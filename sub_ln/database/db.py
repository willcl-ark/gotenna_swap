from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, ForeignKey
from sub_ln import create_random_message
import uuid

engine = create_engine('sqlite:///database.db')
metadata = MetaData()

orders = Table('orders', metadata,
               Column('uuid', String(32), primary_key=True),
               Column('message', String),
               Column('network', String(10)),
               Column('refund_address', String),
               Column('txid', String),
               )

blocksat = Table('blocksat', metadata,
                 Column('uuid', String(32), ForeignKey('orders.uuid'), primary_key=True),
                 Column('satellite_url', String),
                 Column('blocksat_uuid', String),
                 Column('auth_token', String),
                 Column('created_at', Integer),
                 Column('description', String),
                 Column('expires_at', Integer),
                 Column('id', String),
                 Column('sha256_message_digest', String),
                 Column('msatoshi', String),
                 Column('payreq', String),
                 Column('rhash', String),
                 Column('status', String),
                 )

swaps = Table('swaps', metadata,
              Column('uuid', String(32), ForeignKey('orders.uuid'), primary_key=True),
              Column('destination_public_key', String),
              Column('fee_tokens_per_vbyte', Integer),
              Column('invoice', String),
              Column('payment_hash', String),
              Column('redeem_script', String),
              Column('refund_address', String),
              Column('refund_public_key_hash', String),
              Column('swap_amount', Integer),
              Column('swap_fee', Integer),
              Column('swap_key_index', Integer),
              Column('swap_p2sh_address', String),
              Column('swap_p2sh_p2wsh_address', String),
              Column('swap_p2wsh_address', String),
              Column('timeout_block_height', Integer),
              Column('payment_secret', String),
              )

# This will check for the presence of each table first before creating, so it’s safe to call
# multiple times
metadata.create_all(engine)


def add_order(uuid, message):
    conn = engine.connect()
    ins = orders.insert()
    conn.execute(ins, uuid=uuid, message=message)


def add_blocksat(uuid, description):
    conn=engine.connect()
    ins = blocksat.insert()
    conn.execute(ins, uuid=uuid, description=description)


id = str(uuid.uuid4())
msg = create_random_message()
description = msg

add_order(uuid=id, message=msg)
add_blocksat(uuid=id, description=description)



