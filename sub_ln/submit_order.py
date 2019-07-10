import json
import logging
from secrets import token_hex
from time import time, sleep

from sub_ln.authproxy import AuthServiceProxy, JSONRPCException
from blocksat_api import blocksat
from submarine_api import submarine

NETWORK = "testnet"
SATOSHIS = 100_000_000
RPC_HOST = "127.0.0.1"
RPC_PORT = "18332"
RPC_USER = "user"
RPC_PASSWORD = "password"
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger('general')


def create_btc_rpc():
    # logging.debug(f"Setting up bitcoind RawProxy for {NETWORK}")
    return AuthServiceProxy(f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}")


def create_random_message():
    msg = dict()
    i = 0
    while i < 4:
        j = token_hex(12)
        k = token_hex(64)
        msg[j] = k
        i += 1
    message = json.dumps(msg)
    logger.debug(f"Created random message: {message}")
    return message


def check_invoice_details(invoice, network=NETWORK):
    invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
    try:
        assert invoice_details.status_code == 200
        logger.debug(f"Payment Request {invoice['payreq']} successfully decoded by the swap "
                      f"server")
    except AssertionError as e:
        logger.error(f"Check Invoice details raised error: {e}")
        raise e


def check_refund_addr(address):
    check = submarine.get_address_details(address=address, network=NETWORK)
    assert check.status_code == 200
    logger.debug(f"Refund address {address} successfully decoded by the swap server")


class Order:

    def __init__(self, message, network=NETWORK, start_bid_rate=50, max_bid_rate=100):
        self.message = message
        self.btc = create_btc_rpc()
        self.network = network
        self.start_bid_rate = start_bid_rate
        self.max_bid_rate = max_bid_rate
        self.blocksat_order = None
        self.invoice = None
        self.refund_address = None
        self.swap = None
        self.on_chain_receipt = None
        self.logger = logging.getLogger('order')

    def setup_sat_order(self):
        self.blocksat_order = blocksat.Order(message=self.message, network=self.network)
        self.logger.debug(f"Blocksat order created")

    def bid_order(self):
        # bid rate is milli-satoshis/byte
        bid_rate = self.start_bid_rate
        msg_bid = (self.blocksat_order.size * bid_rate)

        # try placing the bid
        self.logger.debug(f"Placing first bid for blocksat order using bid of {msg_bid} milli-satoshis")
        self.blocksat_order.place(bid=msg_bid)

        # if unsuccessful, increase the bid
        while not self.blocksat_order.api_status_code == 200 and bid_rate <= self.max_bid_rate:
            bid_rate = bid_rate + 10
            msg_bid = int(self.blocksat_order.size * bid_rate)
            self.logger.debug(f"Blocksat bid Failed. Increasing bid to {msg_bid} and trying again")
            self.blocksat_order.place(bid=msg_bid)
            sleep(0.5)
        assert self.blocksat_order.api_status_code == 200
        self.logger.debug(f"Blocksat bid accepted using bid of {msg_bid}")
        self.extract_invoice()

    def extract_invoice(self):
        invoice = self.blocksat_order.place_response['lightning_invoice']
        self.logger.debug(f"Extracted invoice from successful blocksat bid")
        check_invoice_details(invoice=invoice, network=self.network)
        self.invoice = invoice

    def get_refund_address(self, type='legacy'):
        address = self.btc.getnewaddress("", type)
        self.logger.debug(f"Got new {type} refund address from bitcoind: {address}")
        check_refund_addr(address)
        self.refund_address = address

    def setup_swap(self):
        self.get_refund_address()
        self.logger.debug(f"Setting up swap request")
        self.swap = submarine.Swap(network=self.network,
                                   invoice=self.invoice['payreq'],
                                   refund=self.refund_address)

    def create_swap(self):
        self.logger.debug("Creating the swap with the swap server")
        self.swap.create()
        try:
            assert self.swap.swap.status_code == 200
            self.logger.debug("Swap created successfully with the server")
        except AssertionError as e:
            raise self.logger.exception((
                self.swap.swap.status_code,
                self.swap.swap.text,
                self.swap.swap.reason))

    def execute_swap(self):
        self.swap.swap_amount_bitcoin = self.swap.swap_amount / SATOSHIS
        self.logger.debug(f"Paying {self.swap.swap_amount_bitcoin} BTC to fulfil the swap")
        self.on_chain_receipt = self.btc.sendtoaddress(
                self.swap.swap_p2sh_address, self.swap.swap_amount_bitcoin)

        # check the on-chain payment
        if self.on_chain_receipt:
            self.logger.debug(f"On-chain swap payment complete, txid: {self.on_chain_receipt}")
        else:
            self.logger.debug("On-chain swap payment using bitcoind failed")

    def check_swap(self):
        self.swap.check_status()
        tries = 0
        self.logger.debug("Waiting for swap approval")
        while self.swap.swap_status.status_code != 200 and tries < 6:
            self.logger.debug(f"Swap not yet approved: {self.swap.swap_status.text}. Trying again")
            self.swap.check_status()
            sleep(10)
            tries += 1
        self.logger.debug("Swap approved\nWaiting for swap server to perform off-chain payment")
        self.wait_for_confirmation(self.on_chain_receipt)
        tries = 0
        while 'payment_secret' not in json.loads(self.swap.swap_status.text) and tries < 6:
            self.swap.check_status()
            self.logger.debug(json.loads(self.swap.swap_status.text))
            sleep(10)
            tries += 1
        if 'payment_secret' in json.loads(self.swap.swap_status.text):
            self.logger.info(f"Swap complete!\n"
                         f"{json.loads(self.swap.swap_status.text)}")
            return True
        else:
            self.logger.debug("Swap not completed within 600 seconds of 1 confirmation")
            return False

    def wait_for_confirmation(self, txid, interval=30):
        self.logger.debug(f"Swap waiting for transaction {txid} to achieve 1 confirmation")
        start = time()
        while self.btc.gettransaction(txid)['confirmations'] < 1:
            sleep(interval)
            current = time() - start
            self.logger.debug(
                f"{self.btc.gettransaction(txid)['confirmations']} after {current} seconds")
        confs = self.btc.gettransaction(txid)['confirmations']
        self.logger.debug(f"Got {confs} confirmations")
        if confs > 0:
            return True
        else:
            return False


if __name__ == "__main__":
    order = Order(create_random_message())
    order.setup_sat_order()
    order.bid_order()
    order.setup_swap()
    order.create_swap()
    order.execute_swap()
    # let the on-chain payment propagate
    sleep(10)
    order.check_swap()
