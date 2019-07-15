import json
import logging
from secrets import token_hex
from time import sleep, time

from blocksat_api import blocksat
from submarine_api import submarine

from sub_ln.authproxy import AuthServiceProxy

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


def create_random_message():
    message = token_hex(64)
    logger.info(f"Created random message: {message}")
    return message


def check_invoice_details(invoice, network=NETWORK):
    invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
    tries = 0
    while invoice_details.status_code != 200 and tries < 10:
        sleep(5)
        invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
    if invoice_details.status_code == 200:
        logger.debug(f"Payment Request {invoice['payreq']} successfully decoded by the swap "
                     f"server")
        return True
    else:
        logger.error(f"Raised error: {invoice_details.text} with invoice\n{invoice_details}")
        return False


def check_refund_addr(address):
    check = submarine.get_address_details(address=address, network=NETWORK)
    assert check.status_code == 200
    logger.debug(f"Refund address {address} successfully decoded by the swap server")


def setup_sat_order(order):
    order.blocksat_order = blocksat.Order(message=order.message, network=order.network)
    order.logger.info("Blocksat order created")


def bid_sat_order(order):
    # bid rate is milli-satoshis/byte
    bid_rate = order.start_bid_rate
    msg_bid = max(order.blocksat_order.size * bid_rate, 10000)

    # try placing the bid
    order.logger.info(f"Placing first bid for blocksat order using bid of {msg_bid} "
                      f"milli-satoshis")
    order.blocksat_order.place(bid=msg_bid)

    # if unsuccessful, increase the bid
    while not order.blocksat_order.api_status_code == 200 and bid_rate <= order.max_bid_rate:
        bid_rate = bid_rate + 10
        msg_bid = int(order.blocksat_order.size * bid_rate)
        order.logger.debug(f"Blocksat bid Failed. Increasing bid to {msg_bid} and trying again")
        order.blocksat_order.place(bid=msg_bid)
        sleep(0.5)
    assert order.blocksat_order.api_status_code == 200
    order.logger.info(f"Blocksat bid accepted using bid of {msg_bid}")
    extract_invoice(order)


def extract_invoice(order):
    # debug/remove if/else
    if 'payreq' in order.invoice:
        assert check_invoice_details(invoice=order.invoice, network=order.network)
    else:
        invoice = order.blocksat_order.place_response['lightning_invoice']
        order.logger.debug(f"Extracted invoice from successful blocksat bid")
        assert check_invoice_details(invoice=invoice, network=order.network)
        order.invoice = invoice


def get_refund_address(order, type='legacy'):
    address = btc_rpc.getnewaddress("", type)
    order.logger.debug(f"Got new {type} refund address from bitcoind: {address}")
    check_refund_addr(address)
    order.refund_address = address


def setup_swap(order):
    get_refund_address(order)
    order.logger.info(f"Setting up swap request")
    order.swap = submarine.Swap(network=order.network,
                                invoice=order.invoice['payreq'],
                                refund=order.refund_address)


def create_swap(order):
    order.logger.info("Creating the swap with the swap server")
    order.swap.create()
    try:
        assert order.swap.swap.status_code == 200
        order.logger.info("Swap created successfully with the server")
    except AssertionError as e:
        raise order.logger.exception((
            order.swap.swap.status_code,
            order.swap.swap.text,
            order.swap.swap.reason))


def execute_swap(order):
    order.swap.swap_amount_bitcoin = order.swap.swap_amount / SATOSHIS
    order.logger.debug(f"Paying {order.swap.swap_amount_bitcoin} BTC to fulfil the swap")
    order.on_chain_receipt = btc_rpc.sendtoaddress(
            order.swap.swap_p2sh_address, order.swap.swap_amount_bitcoin)

    # check the on-chain payment
    if order.on_chain_receipt:
        order.logger.info(f"On-chain swap payment complete, txid: {order.on_chain_receipt}")
    else:
        order.logger.info("On-chain swap payment using bitcoind failed")
    check_swap(order)


def check_swap(order):
    sleep(5)
    order.swap.check_status()
    tries = 0
    order.logger.info("Waiting for swap approval")
    while order.swap.swap_status.status_code != 200 and tries < 6:
        order.logger.debug(f"Swap not yet approved: {order.swap.swap_status.text}. Trying again")
        order.swap.check_status()
        sleep(10)
        tries += 1
    order.logger.info("Swap approved for payment\n"
                      "Waiting for swap server to perform off-chain payment")
    if wait_for_preimage(order):
        return
    else:
        wait_for_confirmation(order, txid=order.on_chain_receipt)
        if wait_for_preimage(order):
            return 1
        else:
            return 0


def wait_for_confirmation(order, txid, interval=30):
    order.logger.info(f"Swap waiting for transaction {txid} to achieve 1 on-chain confirmation")
    start = time()
    while btc_rpc.gettransaction(txid)['confirmations'] < 1:
        sleep(interval)
        current = time() - start
        order.logger.debug(
                f"{btc_rpc.gettransaction(txid)['confirmations']} after {current} seconds")
    confs = btc_rpc.gettransaction(txid)['confirmations']
    order.logger.debug(f"Got {confs} confirmations")
    if confs > 0:
        return True
    else:
        return False


def wait_for_preimage(order, timeout=60):
    order.swap.check_status()
    start_time = time()
    while 'payment_secret' not in json.loads(order.swap.swap_status.text) \
            and time() < start_time + timeout:
        sleep(5)
        order.swap.check_status()
        order.logger.debug(json.loads(order.swap.swap_status.text))
        if BLOCKSAT:
            order.blocksat_order.get()
            order.logger.debug(order.blocksat_order.get_response)
    if 'payment_secret' in json.loads(order.swap.swap_status.text):
        order.logger.info(f"Swap complete!\n"
                          f"{json.loads(order.swap.swap_status.text)}")
        return True
    else:
        order.logger.info("Swap not completed within 60 seconds\n"
                          "Waiting for 1 on-chain confirmation")
        order.wait_for_confirmation(order.on_chain_receipt)
        # TODO: Swap needs to check for payment_secret again here after waiting then return
        return False


def execute_order(order):
    if 'payreq' not in order.invoice:
        logger.debug(f"invoice not found, setting up sat order")
        setup_sat_order(order)
        bid_sat_order(order)
    setup_swap(order)
    create_swap(order)
    execute_swap(order)
