import logging
from uuid import uuid4

from blocksat_api import blocksat
from flask import abort, jsonify
from flask_restful import Resource, reqparse
from submarine_api import submarine

from sub_ln.bitcoin import AuthServiceProxy
from sub_ln.database import db
from sub_ln.server.server_config import RPC_HOST, RPC_PASSWORD, RPC_PORT, RPC_USER
from sub_ln.utilities import create_random_message

logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s - %(levelname)8s - %(name)8s - %(funcName)8s() ] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

bitcoin_rpc = AuthServiceProxy(f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}")


class Rand64ByteMsg(Resource):

    def __init__(self):
        super(Rand64ByteMsg, self).__init__()

    @staticmethod
    def get():
        result = create_random_message()
        return jsonify({'message': result})


class LookupInvoice(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        super(LookupInvoice, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        if 'invoice' not in args:
            abort(400, "Please provide a BOLT11 Payment Request")
        if 'network' not in args:
            abort(400, "Please provide a valid network ('testnet' or 'mainnet')")
        result = submarine.get_invoice_details(invoice=args['invoice'],
                                               network=args['network'])
        # if result.status_code == 200:
        return jsonify({'invoice': result.json()})
        # else:
        #     return result


class CheckRefundAddress(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('address', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        super(CheckRefundAddress, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        if 'address' not in args:
            abort(400, "Please provide a refund address")
        if 'network' not in args:
            abort(400, "Please provide a valid network")
        result = submarine.get_address_details(address=args['address'],
                                               network=args['network']).json()
        return jsonify({'address': result})


class CreateOrder(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('message', type=str, location='json')
        self.reqparse.add_argument('bid', type=str, location='json')
        self.reqparse.add_argument('satellite_url', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        super(CreateOrder, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # testing if/else, will use a random message if non provided
        if 'message' in args:
            msg = args['message']
        else:
            msg = create_random_message()
        # create an order uuid
        uuid = str(uuid4())
        # add order to the orders table
        db.add_order(uuid=uuid, message=msg, network=args['network'])
        # place the blocksat order
        result = blocksat.place(message=args['message'], bid=args['bid'],
                                satellite_url=args['satellite_url']).json()
        # add the order to the blocksat table
        db.add_blocksat(uuid=uuid, satellite_url=args['satellite_url'], result=result)
        return jsonify({'uuid': uuid,
                        'order': result})


class BumpSatOrder(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uuid', type=str, location='json')
        self.reqparse.add_argument('auth_token', type=str, location='json')
        self.reqparse.add_argument('bid_increase', type=str, location='json')
        self.reqparse.add_argument('satellite_url', type=str, location='json')
        super(BumpSatOrder, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        if 'uuid' and 'auth_token' and 'bid_increase' and 'satellite_url' not in args:
            return "Please provide all required json parameters"
        result = blocksat.bump_order(uuid=args['uuid'],
                                     auth_token=args['auth_token'],
                                     bid_increase=args['bid_increase'],
                                     satellite_url=args['satellite_url']).json()
        return jsonify({'order': result})


class GetRefundAddress(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uuid', type=str, location='json')
        self.reqparse.add_argument('type', type=str, location='json')
        super(GetRefundAddress, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        # get a new bitcoin address from rpc
        result = bitcoin_rpc.getnewaddress("", args['type'])
        # add it to the orders table
        db.add_refund_addr(uuid=args['uuid'], refund_addr=result)
        return jsonify({'address': result})


class CreateSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uuid', type=str, location='json')
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        # TODO: Select refund address from db here
        self.reqparse.add_argument('refund_address', type=str, location='json')
        super(CreateSwap, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # create the swap with the swap server
        result = submarine.create(network=args['network'],
                                  invoice=args['invoice'],
                                  refund=args['refund_address']).json()
        # add the swap to the swap table
        db.add_swap(uuid=args['uuid'], result=result)
        return jsonify({'swap': result})


class ExecuteSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uuid', type=str, location='json')
        self.reqparse.add_argument('swap_amount_bitcoin', type=str, location='json')
        self.reqparse.add_argument('swap_p2sh_address', type=str, location='json')
        super(ExecuteSwap, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # TODO: here we can query the db for address and amount
        txid = bitcoin_rpc.sendtoaddress(args['swap_p2sh_address'],
                                         args['swap_amount_bitcoin'])
        db.add_txid(uuid=args['uuid'], txid=txid)
        return jsonify({'txid': txid})


class CheckSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('uuid', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('redeem_script', type=str, location='json')
        super(CheckSwap, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        result = submarine.check_status(network=args['network'],
                                        invoice=args['invoice'],
                                        redeem_script=args['redeem_script']).json()
        # if 'preimage' in result['swap_check']:
        #     db.check_swap(uuid=args['uuid'], preimage=result['swap_check']['preimage'])
        return jsonify({'swap_check': result})
