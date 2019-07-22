# GoTenna Swap

Version 0.0.1

Requires python >=3.6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

An API to send a blockstream blocksat message, which is paid for via an on-chain submarine swap, via the Gotenna mesh network.

## Install requires

* Bitcoin Core

* LND >= v0.7.0-beta

* NPM

* submarineswaps / swaps-service

* Redis


## Installation
#### Cloning and installing source as editable package:

1. Refer to individuation instructions for Bitcoin Core, LND, swaps-service and Redis for installation and configuration.

1. `git clone https://github.com/willcl-ark/gotenna_swap.git`

1. `cd gotenna_swap`

    \* Activate virtual env *

1. `pipenv install` or `pip install -r requirements.txt`

1. `pip install -e .`

1. Edit the values of `gotenna_swap/sub_ln/server/server_config.py` to match your setup. These are used by the API server and database.

### Bitcoin setup

bitcoind must be running on testnet and be ready to accept rpc connections from lnd.

### LND setup

lnd must be running on testnet and ready to accept rpc connections from swap-service 

### swaps-service setup

swaps-service should be cloned from [source](https://github.com/submarineswaps/swaps-service). This package requires `npm v6.10.2` and `nodejs v10.16.0` so update those packages if necessary.

Change into the cloned directory and install dependencies using `npm install`

Recommendation is to then copy `example_env.env` file from `gotenna_swap/sub_ln/example_env.env` to `swap-service/.env` and modify the values to match your setup. You can output your admin.macaroon and tls.cert as base64 with trailing newlines removed to use in the .env file using bash commands:

`base64 -i ~/.lnd/tls.cert | tr -d '\n'`

`base64 -i ~/.lnd/data/chain/bitcoin/testnet/admin.macaroon | tr -d '\n'`


### Redis
Install redis from source or using a package manager like Homebrew. No further setup is required.


## Usage
Start bitcoind and LND on testnet and let them sync.

You can use screen/tmux for the following 3 servers if you prefer:

1. Start redis server. The simplest way to start the Redis server is just executing the redis-server binary without any argument:

    `redis-server`

1. Start the swap-service server:

    `node server.js`

1. Start the gotenna_swap API server. Best activated from within the project sub directory: (`.../gotenna_swap/sub_ln/`), unless you have modified the database directory in `gotenna_swap/sub_ln/server/server_config.py`.

    To run use command: 

    `python server/server.py`

The flask server will now (as default) be running on localhost, port 5000: `http://127.0.0.1:5000`

The file `gotenna_swap/sub_ln/demo.py` shows a practical run-through of API commands and their sequence of usage.