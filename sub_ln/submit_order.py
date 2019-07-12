import argparse
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
logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger('general')


def create_btc_rpc():
    logging.debug(f"Setting up bitcoind RawProxy for {NETWORK}")
    return AuthServiceProxy(f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}")


def create_random_message():
    message = token_hex(64)
    logger.info(f"Created random message: {message}")
    return message


def check_invoice_details(invoice, network=NETWORK):
    invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
    try:
        assert invoice_details.status_code == 200
        logger.debug(f"Payment Request {invoice['payreq']} successfully decoded by the swap "
                     f"server")
    except AssertionError as e:
        logger.error(f"Check Invoice details raised error: {invoice_details.text}")
        logger.error(f"Invoice details:\n{invoice_details}")
        raise e


def check_refund_addr(address):
    check = submarine.get_address_details(address=address, network=NETWORK)
    assert check.status_code == 200
    logger.debug(f"Refund address {address} successfully decoded by the swap server")


class Order:

    def __init__(self, message, network=NETWORK, start_bid_rate=50, max_bid_rate=100, invoice=None):
        self.message = message
        self.btc = create_btc_rpc()
        self.network = network
        self.start_bid_rate = start_bid_rate
        self.max_bid_rate = max_bid_rate
        self.blocksat_order = None
        self.invoice = dict()
        self.refund_address = None
        self.swap = None
        self.on_chain_receipt = None
        self.logger = logging.getLogger('order')
        if invoice:
            self.invoice['payreq'] = invoice

    def setup_sat_order(self):
        self.blocksat_order = blocksat.Order(message=self.message, network=self.network)
        self.logger.info(f"Blocksat order created")

    def bid_order(self):
        # bid rate is milli-satoshis/byte
        bid_rate = self.start_bid_rate
        msg_bid = max(self.blocksat_order.size * bid_rate, 10000)

        # try placing the bid
        self.logger.info(f"Placing first bid for blocksat order using bid of {msg_bid} "
                         f"milli-satoshis")
        self.blocksat_order.place(bid=msg_bid)

        # if unsuccessful, increase the bid
        while not self.blocksat_order.api_status_code == 200 and bid_rate <= self.max_bid_rate:
            bid_rate = bid_rate + 10
            msg_bid = int(self.blocksat_order.size * bid_rate)
            self.logger.debug(f"Blocksat bid Failed. Increasing bid to {msg_bid} and trying again")
            self.blocksat_order.place(bid=msg_bid)
            sleep(0.5)
        assert self.blocksat_order.api_status_code == 200
        self.logger.info(f"Blocksat bid accepted using bid of {msg_bid}")
        self.extract_invoice()

    def extract_invoice(self):
        # debug/remove if/else
        if 'payreq' in self.invoice:
            check_invoice_details(invoice=self.invoice, network=self.network)
            pass
        else:
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
        self.logger.info(f"Setting up swap request")
        self.swap = submarine.Swap(network=self.network,
                                   invoice=self.invoice['payreq'],
                                   refund=self.refund_address)

    def create_swap(self):
        self.logger.info("Creating the swap with the swap server")
        self.swap.create()
        try:
            assert self.swap.swap.status_code == 200
            self.logger.info("Swap created successfully with the server")
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
            self.logger.info(f"On-chain swap payment complete, txid: {self.on_chain_receipt}")
        else:
            self.logger.info("On-chain swap payment using bitcoind failed")
        self.check_swap()

    def check_swap(self):
        sleep(5)
        self.swap.check_status()
        tries = 0
        self.logger.info("Waiting for swap approval")
        while self.swap.swap_status.status_code != 200 and tries < 6:
            self.logger.debug(f"Swap not yet approved: {self.swap.swap_status.text}. Trying again")
            self.swap.check_status()
            sleep(10)
            tries += 1
        self.logger.info("Swap approved for payment\n"
                         "Waiting for swap server to perform off-chain payment")
        if self.wait_for_preimage():
            return
        else:
            self.wait_for_confirmation(txid=self.on_chain_receipt)
            if self.wait_for_preimage():
                return 1
            else:
                return 0

    def wait_for_confirmation(self, txid, interval=30):
        self.logger.info(f"Swap waiting for transaction {txid} to achieve 1 on-chain confirmation")
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

    def wait_for_preimage(self, timeout=60):
        self.swap.check_status()
        start_time = time()
        while 'payment_secret' not in json.loads(self.swap.swap_status.text) \
                and time() < start_time + timeout:
            sleep(5)
            self.swap.check_status()
            self.logger.debug(json.loads(self.swap.swap_status.text))
            if BLOCKSAT:
                self.blocksat_order.get()
                self.logger.debug(self.blocksat_order.get_response)
        if 'payment_secret' in json.loads(self.swap.swap_status.text):
            self.logger.info(f"Swap complete!\n"
                             f"{json.loads(self.swap.swap_status.text)}")
            return True
        else:
            self.logger.info("Swap not completed within 60 seconds\n"
                             "Waiting for 1 on-chain confirmation")
            self.wait_for_confirmation(self.on_chain_receipt)
            # TODO: Swap needs to check for payment_secret again here after waiting then return
            return False


if __name__ == "__main__":

    def main():
        global BLOCKSAT
        parser = argparse.ArgumentParser(description='Perform a submarine swap for a blockstream '
                                                     'blocksat invoice or optionally-provided'
                                                     'invoice')
        parser.add_argument("--invoice",
                            help="Optional BOLT11 payment request to supply for testing. "
                                 "Can't be used with --message", type=str)
        parser.add_argument("--message", help="Optional message to send via the satellite. Can't be"
                                              "used with --invoice", type=str)
        args = parser.parse_args()
        if args.invoice and args.message:
            logger.error("Cannot specify invoice and message together because supplying your own "
                         "message requires a quote from Blockstream API who will return their own "
                         "invoice")
            return
        elif args.invoice:
            order = Order(message=create_random_message(), invoice=args.invoice)
            BLOCKSAT = 0
        elif args.message:
            order = Order(message=args.message)
            order.setup_sat_order()
            order.bid_order()
        else:
            order = Order(message=create_random_message())
            order.setup_sat_order()
            order.bid_order()
        order.setup_swap()
        order.create_swap()
        order.execute_swap()


    main()
