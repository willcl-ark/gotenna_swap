import sqlite3

DATABASE = "/Users/will/Documents/src/go_sat_sub/sub_ln/database.db"


# # initial db setup
# if not os.path.exists(DATABASE):
#     conn = sqlite3.connect(DATABASE)
#     cur = conn.cursor()
#     cur.execute("CREATE TABLE orders ("
#                 "uuid TEXT, "
#                 "message TEXT, "
#                 "network TEXT,"
#                 "start_bid_rate INTEGER, "
#                 "max_bid_rate INTEGER,"
#                 "invoice TEXT,"
#                 "blocksat_auth_token TEXT,"
#                 "blocksat_uuid TEXT,"
#                 "swap_refund TEXT,"
#                 "swap_redeem_script TEXT,"
#                 "swap_p2wsh_address TEXT,"
#                 "swap_timeout_block_height INTEGER,"
#                 "swap_status TEXT);"
#                 )
#     conn.commit()
#     conn.close()

def connection(db=DATABASE):
    try:
        conn = sqlite3.connect(db)
        return conn
    except Exception as e:
        raise e


def create_order(conn, uuid, message, network, start_bid_rate, max_bid_rate):
    c = conn.cursor()
    c.execute("INSERT INTO orders [(uuid, message, network, start_bid_rate, max_bid_rate)] VALUES (uuid, message, network, start_bid_rate, max_bid_rate)")

