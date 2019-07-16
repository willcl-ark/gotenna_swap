# logging config
import logging
from logging.config import fileConfig

# import modules
from sub_ln.authproxy import AuthServiceProxy
from sub_ln.db import DATABASE, connection
from sub_ln.create_random_message import create_random_message
from sub_ln.api import *


# fileConfig('logging.conf')
# logging.getLogger(__name__).addHandler(logging.NullHandler())

