import logging
import time
from json.decoder import JSONDecodeError
from pprint import pformat

import requests
from blocksat_api.blocksat import *
from submarine_api.submarine import *
from sub_ln.bitcoin.authproxy import AuthServiceProxy, JSONRPCException
from sub_ln.server.server_config import RPC_HOST, RPC_PASSWORD, RPC_PORT, RPC_USER

"""
A run-through of an API workflow
"""


URL = "http://127.0.0.1:5000/api/v1/"
SATOSHIS = 100_000_000

logger = logging.getLogger(__name__)
FORMAT = "[%(levelname)s] - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=FORMAT)

bitcoin_rpc = AuthServiceProxy(
    f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}"
)


def fmt_result(result):
    return {"status_code": result.status_code, "Text": result.text}


def main():

    # while True:

    # create the request session
    s = requests.Session()

    # create a random message for testing
    message = s.get(URL + "util/random_message").json()
    logger.debug(f"Created random message:\n{pformat(message)}")

    # create the blocksat order
    blocksat_order = place(
        message=message["message"], bid=10000, satellite_url=TESTNET_SATELLITE_API
    )
    if blocksat_order.status_code == 200:
        blocksat_order = blocksat_order.json()
        logger.debug(f"Created order:\n{pformat(blocksat_order)}")
    else:
        logger.error(
            f"Failed to setup blocksat order:\n{pformat(fmt_result(blocksat_order))}"
        )
        return

    # lookup the returned invoice
    invoice_lookup = get_invoice_details(
        network="testnet", invoice=blocksat_order["lightning_invoice"]["payreq"]
    )
    if invoice_lookup.status_code == 200:
        logger.debug(f"Successfully looked up invoice with swap server")
    else:
        logger.error(
            f"Failed invoice lookup with swap server:\n{pformat(fmt_result(invoice_lookup))}"
        )
        return

    # Get a refund address for the swap
    refund_address = bitcoin_rpc.getnewaddress("", "legacy")

    # create the swap with swap server
    create_swap = get_quote(
        network="testnet",
        invoice=blocksat_order["lightning_invoice"]["payreq"],
        refund=refund_address,
    )
    if create_swap.status_code == 200:
        create_swap = create_swap.json()
        logging.debug(f"Successfully created the swap request with swap server")
    else:
        logging.error(
            f"Failed to setup the swap request with the server:\n{pformat(fmt_result(create_swap))}"
        )
        return

    # pay on-chain swap payment
    swap_amt_bitcoin = create_swap["swap_amount"] / SATOSHIS
    txid = bitcoin_rpc.sendtoaddress(create_swap["swap_p2sh_address"], swap_amt_bitcoin)

    # check the swap status
    swap_status = check_status(
        network="testnet",
        invoice=blocksat_order["lightning_invoice"]["payreq"],
        redeem_script=create_swap["redeem_script"],
    )

    # wait for completion
    logger.debug(f"Swap status:\n{pformat(fmt_result(swap_status))}")
    tries = 0
    complete = False

    while not complete and tries < 60:
        time.sleep(5)
        swap_status = check_status(
            network="testnet",
            invoice=blocksat_order["lightning_invoice"]["payreq"],
            redeem_script=create_swap["redeem_script"],
        )
        logger.debug(f"Swap status:\n{pformat(fmt_result(swap_status))}")
        if "payment_secret" in swap_status.json():
            complete = True
        tries += 1


if __name__ == "__main__":
    main()
