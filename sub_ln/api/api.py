import logging
from json.decoder import JSONDecodeError
from uuid import uuid4

from blocksat_api import blocksat
from flask import jsonify, make_response
from flask_restful import Resource, reqparse
from submarine_api import submarine

from sub_ln.bitcoin import AuthServiceProxy, JSONRPCException
from sub_ln.database import db
from sub_ln.server.server_config import RPC_HOST, RPC_PASSWORD, RPC_PORT, RPC_USER
from sub_ln.utilities import create_random_message

logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s - %(levelname)8s - %(name)8s - %(funcName)8s() ] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

bitcoin_rpc = AuthServiceProxy(
    f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}"
)

SAT_PER_BTC = 100_000_000


class Rand64ByteMsg(Resource):
    """
    Returns a 64 byte random message for testing.
    """

    def __init__(self):
        super(Rand64ByteMsg, self).__init__()

    @staticmethod
    def get():
        result = create_random_message()
        return make_response(jsonify({"message": result}), 200)


class SwapLookupInvoice(Resource):
    """
    Looks up the Invoice related to the swap using the swap server (which in turn queries LND).

    This is an important part of route-finding to determine, before the user sends funds, whether
    the swap server will be able to pay this invoice, or if they can, what fees they need to charge.

    This is called internally as part of submarine.check_swap(), but it's good practice to manually
    verify early on.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("invoice", type=str, location="json")
        self.reqparse.add_argument("network", type=str, location="json")
        super(SwapLookupInvoice, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        result = submarine.get_invoice_details(
            invoice=args["invoice"], network=args["network"]
        )
        try:
            return make_response(jsonify({"invoice": result.json()}), 200)
        except Exception as e:
            raise jsonify({"exception": e, "result": result})


class SwapCheckRefundAddress(Resource):
    """
    Checks that the refund address provided is correct for the currency and network so that failed
    swaps can be refunded in a non-custodial fashion.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("address", type=str, location="json")
        self.reqparse.add_argument("network", type=str, location="json")
        super(SwapCheckRefundAddress, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        result = submarine.get_address_details(
            address=args["address"], network=args["network"]
        )
        try:
            return make_response(jsonify({"address": result.json()}), 200)
        except Exception as e:
            raise jsonify({"exception": e, "result": result})


class CreateOrder(Resource):
    """
    Create the initial order in the DB.

    This API will both create a unique GoTenna order, and also perform the initial order submission
    to the Blocksat API.

    The uuid (*not* 'blockstream_uuid' which is different!) returned from this request should be
    used in subsequent API calls as the order identifier.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("message", type=str, location="json")
        self.reqparse.add_argument("bid", type=str, location="json")
        self.reqparse.add_argument("satellite_url", type=str, location="json")
        self.reqparse.add_argument("network", type=str, location="json")
        super(CreateOrder, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        msg = args["message"]
        uuid = str(uuid4())
        db.add_order(uuid=uuid, message=msg, network=args["network"])
        result = blocksat.place(
            message=args["message"],
            bid=args["bid"],
            satellite_url=args["satellite_url"],
        )
        try:
            result = result.json()
            db.add_blocksat(
                uuid=uuid, satellite_url=args["satellite_url"], result=result
            )
            return make_response(jsonify({"uuid": uuid, "order": result}), 200)
        except Exception as e:
            raise jsonify({"exception": e, "result": result})


class BlocksatBump(Resource):
    """
    Bump the fee associated with an existing blocksat order.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("uuid", type=str, location="json")
        self.reqparse.add_argument("bid_increase", type=str, location="json")
        super(BlocksatBump, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # lookup the order from blocksat table
        blocksat_uuid, auth_token, satellite_url = db.lookup_bump(uuid=args["uuid"])
        # bump the order using the details
        result = blocksat.bump_order(
            uuid=blocksat_uuid,
            auth_token=auth_token,
            bid_increase=args["bid_increase"],
            satellite_url=satellite_url,
        )
        try:
            result = result.json()
            # TODO: update the database here
            return make_response(jsonify({"order": result}), 200)
        except Exception as e:
            raise jsonify({"exception": e, "result": result})


class GetRefundAddress(Resource):
    """
    Get a refund address of type 'type' from bitcoind connection and associate it with the order
    Recommended to use type='legacy' for maximum compatibility
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("uuid", type=str, location="json")
        self.reqparse.add_argument("type", type=str, location="json")
        super(GetRefundAddress, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        # get a new bitcoin address from rpc
        try:
            result = bitcoin_rpc.getnewaddress("", args["type"])
            # add it to the orders table
            db.add_refund_addr(uuid=args["uuid"], refund_addr=result)
            return make_response(jsonify({"address": result}), 200)
        except JSONRPCException as e:
            raise jsonify({"exception": e})


class SwapQuote(Resource):
    """
    Create and return the swap quote from the swap server
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("uuid", type=str, location="json")
        self.reqparse.add_argument("invoice", type=str, location="json")
        self.reqparse.add_argument("network", type=str, location="json")
        # TODO: Select refund address from db here
        self.reqparse.add_argument("refund_address", type=str, location="json")
        super(SwapQuote, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        # search the refund addr from the db
        refund_address = db.lookup_refund_addr(args["uuid"])[0]
        result = submarine.get_quote(
            network=args["network"], invoice=args["invoice"], refund=refund_address
        )
        try:
            result = result.json()
            db.add_swap(uuid=args["uuid"], result=result)
            return make_response(jsonify({"swap": result}), 200)
        except Exception as e:
            raise jsonify({"exception": e, "result": result})


class SwapPay(Resource):
    """
    Pay the on-chain part of the swap
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("uuid", type=str, location="json")
        super(SwapPay, self).__init__()

    def post(self):
        args = self.reqparse.parse_args(strict=True)
        swap_amount, swap_p2sh_address = db.lookup_pay_details(args["uuid"])
        swap_amount_bitcoin = swap_amount / SAT_PER_BTC
        logger.debug(f"swap_amount_bitcoin: {swap_amount_bitcoin}")
        try:
            txid = bitcoin_rpc.sendtoaddress(swap_p2sh_address, swap_amount_bitcoin)
            db.add_txid(uuid=args["uuid"], txid=txid)
            return jsonify({"txid": txid})
        except JSONRPCException as e:
            raise jsonify({"exception": e})


class SwapCheck(Resource):
    """
    Check the swap. This will also check the funding status of swaps, prompting the server to pay an
    invoice for a newly-funded swap, although this also happens periodically automatically.
    """

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("uuid", type=str, location="json")
        super(SwapCheck, self).__init__()

    def get(self):
        args = self.reqparse.parse_args(strict=True)
        # lookup swap details here
        network, invoice, redeem_script = db.lookup_swap_details(args["uuid"])
        result = submarine.check_status(
            network=network, invoice=invoice, redeem_script=redeem_script
        )
        try:
            return jsonify({"swap_check": result.json()})
        except Exception as e:
            raise jsonify({"exception": e, "result": result})
