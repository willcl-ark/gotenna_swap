import logging
from uuid import uuid1

# FORMAT = "[%(asctime)s - %(levelname)8s - %(funcName)20s() ] - %(message)s"
# logging.basicConfig(level=logging.DEBUG, format=FORMAT)


class Order:

    def __init__(self, message="", network='testnet', start_bid_rate=50, max_bid_rate=100,
                 invoice=None):
        self.uuid = uuid1()
        self.message = message
        self.network = network
        self.start_bid_rate = start_bid_rate
        self.max_bid_rate = max_bid_rate
        self.blocksat_order = None
        self.invoice = dict()
        self.refund_address = None
        self.swap = None
        self.on_chain_receipt = None
        self.logger = logging.getLogger(f'order ...{self.uuid.hex[:6]}')
        if invoice:
            self.invoice['payreq'] = invoice

    def __repr__(self):
        return f"Order({self.message}, " \
            f"{self.network}, " \
            f"{self.start_bid_rate}, " \
            f"{self.max_bid_rate}, " \
            f"{self.invoice})"

    def __str__(self):
        return f"Order {self.uuid} with message: {self.message} and invoice: {self.invoice}"
