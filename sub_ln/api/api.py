from blocksat_api import blocksat
from flask import Flask, abort, jsonify
from flask_restful import Api, Resource, reqparse
from submarine_api import submarine

from sub_ln import *

BLOCKSAT = 1
NETWORK = "testnet"
SATOSHIS = 100_000_000
RPC_HOST = "127.0.0.1"
RPC_PORT = "18332"
RPC_USER = "user"
RPC_PASSWORD = "password"

logger = logging.getLogger('API')
FORMAT = "[%(asctime)s - %(levelname)8s - %(funcName)20s() ] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

bitcoin_rpc = AuthServiceProxy(f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}")

app = Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)


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
                                               network=args['network']).json()
        return jsonify({'invoice': result})


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
        super(CreateOrder, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # testing if/else
        if 'message' in args:
            msg = args['message']
        else:
            msg = create_random_message()
        # should write the order to db and return the uuid
        result = blocksat.place(message=args['message'], bid=args['bid'],
                                satellite_url=args['satellite_url']).json()
        return jsonify({'order': result})


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
        self.reqparse.add_argument('type', type=str, location='json')
        super(GetRefundAddress, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        result = bitcoin_rpc.getnewaddress("", args['type'])
        return jsonify({'address': result})


class CreateSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        self.reqparse.add_argument('refund_address', type=str, location='json')
        super(CreateSwap, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        result = submarine.create(network=args['network'],
                                  invoice=args['invoice'],
                                  refund=args['refund_address']).json()
        return jsonify({'swap': result})


class ExecuteSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('swap_amount_bitcoin', type=str, location='json')
        self.reqparse.add_argument('swap_p2sh_address', type=str, location='json')
        super(ExecuteSwap, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        on_chain_receipt = bitcoin_rpc.sendtoaddress(args['swap_p2sh_address'],
                                                     args['swap_amount_bitcoin'])
        return jsonify({'txid': on_chain_receipt})


class CheckSwap(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('network', type=str, location='json')
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('redeem_script', type=str, location='json')
        super(CheckSwap, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        result = submarine.check_status(network=args['network'],
                                        invoice=args['invoice'],
                                        redeem_script=args['redeem_script']).json()
        return jsonify({'swap_check': result})


api.add_resource(Rand64ByteMsg, '/api/v1/util/random_message')
api.add_resource(LookupInvoice, '/api/v1/swap/lookup_invoice')
api.add_resource(CheckRefundAddress, '/api/v1/swap/check_refund_address')
api.add_resource(CreateOrder, '/api/v1/blocksat/create_order')
api.add_resource(BumpSatOrder, '/api/v1/blocksat/bump_order')
api.add_resource(GetRefundAddress, '/api/v1/bitcoin/get_new_address')
api.add_resource(CreateSwap, '/api/v1/swap/create_swap')
api.add_resource(ExecuteSwap, '/api/v1/swap/execute_swap')
api.add_resource(CheckSwap, '/api/v1/swap/check_swap')

app.run()
