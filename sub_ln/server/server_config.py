# General
SATOSHIS = 100_000_000

# Bitcoin
NETWORK = "testnet"
RPC_HOST = "127.0.0.1"
RPC_PORT = "18332"
RPC_USER = "user"
RPC_PASSWORD = "password"

# Database
# Database path is relative to the CWD the server is run from
# It will create a .db file automatically, but if the directory structure does not
# exist will raise an `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
# unable to open database file`
DB_PATH = "database/database.db"
