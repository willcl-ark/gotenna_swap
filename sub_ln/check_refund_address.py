import logging
from submarine_api import submarine

logger = logging.getLogger(__name__)


def check_refund_address(address, network):
    check = submarine.get_address_details(address=address,
                                          network=network)
    logger.debug(f"Refund address {address} successfully decoded by the swap server")
    return check