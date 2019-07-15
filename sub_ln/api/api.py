from flask import Flask, jsonify, abort, make_response
from flask_restful import Api, Resource, fields, reqparse
import json
import logging
from time import sleep, time

from sub_ln import *
from blocksat_api import blocksat
from submarine_api import submarine


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

btc_rpc = AuthServiceProxy(f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}")

app = Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)


class Rand64ByteMsg(Resource):

    def __init__(self):
        super(Rand64ByteMsg, self).__init__()

    @staticmethod
    def get():
        message = create_random_message()
        return {'message': message}


class LookupInvoice(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('invoice', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        super(LookupInvoice, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        if 'invoice' not in args:
            abort(400, "Please provide a BOLT11 Payment Request")
        if 'network' not in args:
            abort(400, "Please provide a valid network ('testnet' or 'mainnet')")
        return check_invoice_details(args['invoice'], args['network']).json()


class CheckRefundAddress(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('address', type=str, location='json')
        self.reqparse.add_argument('network', type=str, location='json')
        super(CheckRefundAddress, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        if 'address' not in args:
            abort(400, "Please provide a refund address")
        if 'network' not in args:
            abort(400, "Please provide a valid network")
        return check_refund_address(args['address'], args['network']).json()


# def create_order(message, invoice, network, start_bid_rate, max_bid_rate):
#     if message:
#         msg = message
#     else:
#         msg = create_random_message()
#     if invoice:
#         inv = invoice
#     # should write the order to db and return the uuid
#     return Order(message=msg,
#                  network=network,
#                  start_bid_rate=start_bid_rate,
#                  max_bid_rate=max_bid_rate
#                  )
#
#
# def lookup_order(order_uuid):
#     # lookup the order from the db and return details
#     pass
#
#
# def setup_sat_order(order):
#     order.blocksat_order = blocksat.Order(message=order.message, network=order.network)
#     order.logger.info("Blocksat order created")
#
#
# def bid_sat_order(order):
#     # bid rate is milli-satoshis/byte
#     bid_rate = order.start_bid_rate
#     msg_bid = max(order.blocksat_order.size * bid_rate, 10000)
#
#     # try placing the bid
#     order.logger.info(f"Placing first bid for blocksat order using bid of {msg_bid} "
#                       f"milli-satoshis")
#     order.blocksat_order.place(bid=msg_bid)
#
#     # if unsuccessful, increase the bid
#     while not order.blocksat_order.api_status_code == 200 and bid_rate <= order.max_bid_rate:
#         bid_rate = bid_rate + 10
#         msg_bid = int(order.blocksat_order.size * bid_rate)
#         order.logger.debug(f"Blocksat bid Failed. Increasing bid to {msg_bid} and trying again")
#         order.blocksat_order.place(bid=msg_bid)
#         sleep(0.5)
#     assert order.blocksat_order.api_status_code == 200
#     order.logger.info(f"Blocksat bid accepted using bid of {msg_bid}")
#     extract_invoice(order)
#
#
# def extract_invoice(order):
#     # debug/remove if/else
#     if 'payreq' in order.invoice:
#         assert check_invoice_details(invoice=order.invoice, network=order.network)
#     else:
#         invoice = order.blocksat_order.place_response['lightning_invoice']
#         order.logger.debug(f"Extracted invoice from successful blocksat bid")
#         assert check_invoice_details(invoice=invoice, network=order.network)
#         order.invoice = invoice
#
#
# def get_refund_address(order, type='legacy'):
#     address = btc_rpc.getnewaddress("", type)
#     order.logger.debug(f"Got new {type} refund address from bitcoind: {address}")
#     check_refund_addr(address)
#     order.refund_address = address
#
#
# def setup_swap(order):
#     get_refund_address(order)
#     order.logger.info(f"Setting up swap request")
#     order.swap = submarine.Swap(network=order.network,
#                                 invoice=order.invoice['payreq'],
#                                 refund=order.refund_address)
#
#
# def create_swap(order):
#     order.logger.info("Creating the swap with the swap server")
#     order.swap.create()
#     try:
#         assert order.swap.swap.status_code == 200
#         order.logger.info("Swap created successfully with the server")
#     except AssertionError as e:
#         raise order.logger.exception((
#             order.swap.swap.status_code,
#             order.swap.swap.text,
#             order.swap.swap.reason))
#
#
# def execute_swap(order):
#     order.swap.swap_amount_bitcoin = order.swap.swap_amount / SATOSHIS
#     order.logger.debug(f"Paying {order.swap.swap_amount_bitcoin} BTC to fulfil the swap")
#     order.on_chain_receipt = btc_rpc.sendtoaddress(
#             order.swap.swap_p2sh_address, order.swap.swap_amount_bitcoin)
#
#     # check the on-chain payment
#     if order.on_chain_receipt:
#         order.logger.info(f"On-chain swap payment complete, txid: {order.on_chain_receipt}")
#     else:
#         order.logger.info("On-chain swap payment using bitcoind failed")
#     check_swap(order)
#
#
# def check_swap(order):
#     sleep(5)
#     order.swap.check_status()
#     tries = 0
#     order.logger.info("Waiting for swap approval")
#     while order.swap.swap_status.status_code != 200 and tries < 6:
#         order.logger.debug(f"Swap not yet approved: {order.swap.swap_status.text}. Trying again")
#         order.swap.check_status()
#         sleep(10)
#         tries += 1
#     order.logger.info("Swap approved for payment\n"
#                       "Waiting for swap server to perform off-chain payment")
#     if wait_for_preimage(order):
#         return
#     else:
#         wait_for_confirmation(order, txid=order.on_chain_receipt)
#         if wait_for_preimage(order):
#             return 1
#         else:
#             return 0
#
#
# def wait_for_confirmation(order, txid, interval=30):
#     order.logger.info(f"Swap waiting for transaction {txid} to achieve 1 on-chain confirmation")
#     start = time()
#     while btc_rpc.gettransaction(txid)['confirmations'] < 1:
#         sleep(interval)
#         current = time() - start
#         order.logger.debug(
#                 f"{btc_rpc.gettransaction(txid)['confirmations']} after {current} seconds")
#     confs = btc_rpc.gettransaction(txid)['confirmations']
#     order.logger.debug(f"Got {confs} confirmations")
#     if confs > 0:
#         return True
#     else:
#         return False
#
#
# def wait_for_preimage(order, timeout=60):
#     order.swap.check_status()
#     start_time = time()
#     while 'payment_secret' not in json.loads(order.swap.swap_status.text) \
#             and time() < start_time + timeout:
#         sleep(5)
#         order.swap.check_status()
#         order.logger.debug(json.loads(order.swap.swap_status.text))
#         if BLOCKSAT:
#             order.blocksat_order.get()
#             order.logger.debug(order.blocksat_order.get_response)
#     if 'payment_secret' in json.loads(order.swap.swap_status.text):
#         order.logger.info(f"Swap complete!\n"
#                           f"{json.loads(order.swap.swap_status.text)}")
#         return True
#     else:
#         order.logger.info("Swap not completed within 60 seconds\n"
#                           "Waiting for 1 on-chain confirmation")
#         order.wait_for_confirmation(order.on_chain_receipt)
#         # TODO: Swap needs to check for payment_secret again here after waiting then return
#         return False
#
#
# def execute_order(order):
#     if 'payreq' not in order.invoice:
#         logger.debug(f"invoice not found, setting up sat order")
#         setup_sat_order(order)
#         bid_sat_order(order)
#     setup_swap(order)
#     create_swap(order)
#     execute_swap(order)


api.add_resource(Rand64ByteMsg, '/api/v1/utilities/random_message')
api.add_resource(LookupInvoice, '/api/v1/submarine/lookup_invoice')
api.add_resource(CheckRefundAddress, '/api/v1/submarine/check_refund_address')

app.run()