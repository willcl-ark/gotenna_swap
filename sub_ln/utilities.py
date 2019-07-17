import logging
from secrets import token_hex

logger = logging.getLogger(__name__)


def create_random_message():
    message = str(token_hex(64))
    logger.info(f"Created random message: {message}")
    return message
