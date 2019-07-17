# import logging
from flask import Flask
from flask_restful import Api

from sub_ln.api.api import BumpSatOrder, CheckRefundAddress, CheckSwap, CreateOrder, CreateSwap, \
    ExecuteSwap, GetRefundAddress, LookupInvoice, Rand64ByteMsg

# logger = logging.getLogger('API')
# FORMAT = "[%(asctime)s - %(levelname)8s - %(funcName)20s() ] - %(message)s"
# logging.basicConfig(level=logging.DEBUG, format=FORMAT)


app = Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)

api.add_resource(Rand64ByteMsg, '/api/v1/util/random_message')
api.add_resource(LookupInvoice, '/api/v1/swap/lookup_invoice')
api.add_resource(CheckRefundAddress, '/api/v1/swap/check_refund_address')
api.add_resource(CreateOrder, '/api/v1/blocksat/create_order')
api.add_resource(BumpSatOrder, '/api/v1/blocksat/bump_order')
api.add_resource(GetRefundAddress, '/api/v1/bitcoin/get_new_address')
api.add_resource(CreateSwap, '/api/v1/swap/create_swap')
api.add_resource(ExecuteSwap, '/api/v1/swap/execute_swap')
api.add_resource(CheckSwap, '/api/v1/swap/check_swap')

app.run()
