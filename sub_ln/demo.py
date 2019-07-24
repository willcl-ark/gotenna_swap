import logging
import requests
import time

from pprint import pformat

from sub_ln.utilities import clock

"""
A run-through of an API workflow
"""


URL = "http://127.0.0.1:5000/api/v1/"
SATOSHIS = 100_000_000

logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s - %(levelname)s] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)


# create the request session
s = requests.Session()


@clock
def create_message():
    message = s.get(URL + "util/random_message").json()
    logger.debug(f"Created random message:\n{pformat(message)}")
    return message


@clock
def create_blocksat_order(message):
    order_params = {"message": message["message"], "bid": 10000, "network": "testnet"}
    blocksat_order = s.post(URL + "order/create", json=order_params)
    if blocksat_order.status_code == 200:
        blocksat_order = blocksat_order.json()
        logger.debug(
            f"Created order: {blocksat_order['uuid']} for blocksat order:\n"
            f"{pformat(blocksat_order['order'])}"
        )
        return blocksat_order
    else:
        logger.error(f"Failed to setup blocksat order")
        return 0


@clock
def lookup_invoice(blocksat_order):
    invoice_params = {
        "invoice": blocksat_order["order"]["lightning_invoice"]["payreq"],
        "network": "testnet",
    }
    invoice_lookup = s.get(URL + "swap/lookup_invoice", json=invoice_params)
    if invoice_lookup.status_code == 200:
        invoice_lookup = invoice_lookup.json()
        logger.debug(f"Successfully looked up invoice with swap server")
        return invoice_lookup
    else:
        logger.error(
            f"Failed invoice lookup with swap server\n"
            f"{pformat({'code': invoice_lookup.status_code, 'text': invoice_lookup.text})}"
        )
        return 0


@clock
def get_refund_addr(uuid):
    refund_params = {"uuid": uuid, "type": "legacy"}
    refund_address = s.get(URL + "bitcoin/new_address", json=refund_params)
    if refund_address.status_code == 200:
        refund_address = refund_address.json()
        logging.debug(
            f"Successfully got refund address {refund_address['address']} for the swap"
        )
        return refund_address
    else:
        logger.error(f"Failed to get a refund address")
        return 0


@clock
def create_swap_func(uuid, blocksat_order, refund_address):
    create_swap_params = {
        "uuid": uuid,
        "invoice": blocksat_order["order"]["lightning_invoice"]["payreq"],
        "network": "testnet",
        "refund_address": refund_address["address"],
    }
    _create_swap = s.post(URL + "swap/quote", json=create_swap_params)
    if _create_swap.status_code == 200:
        _create_swap = _create_swap.json()
        logging.debug(
            f"Successfully created the swap request with swap server:\n"
            f"{pformat(_create_swap)}"
        )
        return _create_swap
    else:
        logging.error(f"Failed to setup the swap request with the server")
        return 0


@clock
def pay_swap_func(uuid):
    pay_swap_params = {"uuid": uuid}
    pay_swap = s.post(URL + "swap/pay", json=pay_swap_params)
    logging.debug(f"pay_swap: {pformat(pay_swap.text)}")
    pay_swap = pay_swap.json()
    if "txid" in pay_swap:
        logger.debug(
            f"Successfully executed on-chain payment for swap, txid: {pay_swap['txid']}"
        )
        return pay_swap
    return 0


@clock
def check_swp_status(uuid):
    swap_status_params = {"uuid": uuid}

    tries = 0
    complete = False

    while not complete and tries < 60:
        time.sleep(5)
        swap_status = s.get(URL + "swap/check", json=swap_status_params).json()
        logger.debug(f"Swap status:\n{pformat(swap_status)}")
        if "payment_secret" in swap_status["swap_check"]:
            complete = True
        tries += 1

    if not complete:
        logger.error(f"Failed to received preimage for payment, swap not complete")


def main():

    # create a random message for testing
    message = create_message()

    # create the blocksat order
    blocksat_order = create_blocksat_order(message)
    if not blocksat_order:
        return

    # set our order uuid to one returned by API (not blocksat_order.blocksat_uuid though!)
    uuid = blocksat_order["uuid"]

    # # bump the order fee
    # bid_increase = 5000
    # bump_json = {'uuid': uuid,
    #              'bid_increase': bid_increase}
    # blocksat_order_bump = s.post(URL + 'blocksat/bump', json=bump_json).json()
    # if 'payreq' in blocksat_order_bump['order']['lightning_invoice']:
    #     logger.debug(f"Successfully bumped the fee of the blocksat order by {bid_increase}")

    # lookup the returned invoice
    invoice_lookup = lookup_invoice(blocksat_order)
    if not invoice_lookup:
        return

    # Get a refund address for the swap
    refund_address = get_refund_addr(uuid)
    if not refund_address:
        return

    # create the swap with swap server
    # TODO: Fix so that only requires uuid
    create_swap = create_swap_func(uuid, blocksat_order, refund_address)
    if not create_swap:
        return

    # pay on-chain swap payment
    pay_swap = pay_swap_func(uuid)
    if not pay_swap:
        return

    # check the swap status
    check_swp_status(uuid)

    # TODO: should check the blockstream order status here
    #   to make super sure it's been accepted


if __name__ == "__main__":
    main()
