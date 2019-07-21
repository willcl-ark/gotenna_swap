from flask import Flask
from flask_restful import Api

from sub_ln.api.api import (
    BlocksatBump,
    SwapCheckRefundAddress,
    SwapCheck,
    CreateOrder,
    SwapQuote,
    SwapPay,
    GetRefundAddress,
    SwapLookupInvoice,
    Rand64ByteMsg,
)
from sub_ln.database import db


# setup the Flask app
app = Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)

# add the API endpoints
api.add_resource(Rand64ByteMsg, "/api/v1/util/random_message")
api.add_resource(SwapLookupInvoice, "/api/v1/swap/lookup_invoice")
api.add_resource(SwapCheckRefundAddress, "/api/v1/swap/check_refund_addr")
api.add_resource(CreateOrder, "/api/v1/order/create")
api.add_resource(BlocksatBump, "/api/v1/blocksat/bump")
api.add_resource(GetRefundAddress, "/api/v1/bitcoin/new_address")
api.add_resource(SwapQuote, "/api/v1/swap/quote")
api.add_resource(SwapPay, "/api/v1/swap/pay")
api.add_resource(SwapCheck, "/api/v1/swap/check")

# initialise the db, this will check for presence of tables before creating, so safe
# to call multiple times
db.init()

# start the API server
app.run()
