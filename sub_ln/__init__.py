# logging config
import logging
from logging.config import fileConfig

# import modules
from sub_ln.authproxy import AuthServiceProxy
from sub_ln.create_random_message import create_random_message
from sub_ln.check_inv_details import check_invoice_details
from sub_ln.check_refund_address import check_refund_address


fileConfig('logging.conf')
logging.getLogger(__name__).addHandler(logging.NullHandler())

