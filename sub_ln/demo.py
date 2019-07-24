import logging
import requests
import time

from json.decoder import JSONDecodeError
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


def main():

    # create the request session
    s = requests.Session()

    # create a random message for testing
    message = s.get(URL + "util/random_message").json()
    logger.debug(f"Created random message:\n{pformat(message)}")

    # create the blocksat order
    order_params = {"message": message["message"], "bid": 10000, "network": "testnet"}
    blocksat_order = s.post(URL + "order/create", json=order_params)
    if blocksat_order.status_code == 200:
        blocksat_order = blocksat_order.json()
        logger.debug(
            f"Created order: {blocksat_order['uuid']} for blocksat order:\n{pformat(blocksat_order['order'])}"
        )
    else:
        logger.error(f"Failed to setup blocksat order")
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

    time.sleep(5)
    # lookup the returned invoice
    invoice_params = {
        "invoice": blocksat_order["order"]["lightning_invoice"]["payreq"],
        "network": "testnet",
    }
    invoice_lookup = s.get(URL + "swap/lookup_invoice", json=invoice_params)
    if invoice_lookup.status_code == 200:
        invoice_lookup = invoice_lookup.json()
        logger.debug(f"Successfully looked up invoice with swap server")
    else:
        logger.error(f"Failed invoice lookup with swap server\n{pformat({'code': invoice_lookup.status_code, 'text': invoice_lookup.text})}")
        return

    time.sleep(2)
    # Get a refund address for the swap
    refund_params = {"uuid": uuid, "type": "legacy"}
    refund_address = s.get(URL + "bitcoin/new_address", json=refund_params)
    if refund_address.status_code == 200:
        refund_address = refund_address.json()
        logging.debug(
            f"Successfully got refund address {refund_address['address']} for the swap"
        )
    else:
        logger.error(f"Failed to get a refund address")
        return

    time.sleep(2)
    # create the swap with swap server
    create_swap_params = {
        "uuid": uuid,
        "invoice": blocksat_order["order"]["lightning_invoice"]["payreq"],
        "network": "testnet",
        "refund_address": refund_address["address"],
    }
    create_swap = s.post(URL + "swap/quote", json=create_swap_params)
    if create_swap.status_code == 200:
        create_swap = create_swap.json()
        logging.debug(f"Successfully created the swap request with swap server:\n"
                      f"{pformat(create_swap)}")
    else:
        logging.error(f"Failed to setup the swap request with the server")
        return

    time.sleep(10)
    # pay on-chain swap payment
    pay_swap_params = {"uuid": uuid}
    pay_swap = s.post(URL + "swap/pay", json=pay_swap_params)
    logging.debug(f"pay_swap: {pformat(pay_swap)}")
    pay_swap = pay_swap.json()
    if "txid" in pay_swap:
        logger.debug(
            f"Successfully executed on-chain payment for swap, txid: {pay_swap['txid']}"
        )

    time.sleep(20)
    # check the swap status
    swap_status_params = {"uuid": uuid}

    swap_status = s.get(URL + "swap/check", json=swap_status_params).json()
    tries = 0
    complete = False

    while tries < 10:
        try:
            swap_status = s.get(URL + "swap/check_swap", json=swap_status_params).json()
        except JSONDecodeError as e:
            print("Ouch")
            logger.debug(e)
            pass
        tries += 1
        time.sleep(10)
        if "payment_secret" in swap_status["swap_check"]:
            logger.debug(
                f"Payment complete! Preimage: {swap_status['swap_check']['payment_secret']}"
            )
            complete = True
            break

    if not complete:
        logger.error(f"Failed to received preimage for payment, swap not complete")

    # TODO: should check the blockstream order status here
    #   to make super sure it's been accepted


if __name__ == "__main__":
    main()
