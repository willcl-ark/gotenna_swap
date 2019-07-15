from submarine_api import submarine
from time import sleep
import logging

logger = logging.getLogger(__name__)


def check_invoice_details(invoice, network):
    invoice_details = submarine.get_invoice_details(network=network, invoice=invoice)
    tries = 0
    while invoice_details.status_code != 200 and tries < 5:
        sleep(5)
        invoice_details = submarine.get_invoice_details(network=network, invoice=invoice)
    if invoice_details.status_code == 200:
        logger.debug(f"Payment Request {invoice} successfully decoded by the swap "
                     f"server")
    else:
        logger.error(f"Raised error: {invoice_details.text} with invoice\n{invoice_details}")
    return invoice_details
