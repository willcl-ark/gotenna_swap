import json
from secrets import token_hex
from time import sleep

import bitcoin.rpc
from blocksat_api import blocksat
from submarine_api import submarine

NETWORK = 'testnet'
SATOSHIS = 100_000_000

# create random 64 byte message to be sent
message = token_hex(256)

# setup the satellite Order
sat = blocksat.Order(message=message, network=NETWORK)
# note bid is in milli-satoshis
bid_msat = (sat.size * 50) * 2
sat.place(bid=bid_msat)
if sat.api_status_code == 200:
    pass
else:
    while not sat.api_status_code == 200:
        bid_msat = bid_msat + 10
        sat.place(bid=bid_msat)
        sleep(2)
invoice = sat.place_response['lightning_invoice']

# setup bitcoin core proxy
proxy = bitcoin.rpc.RawProxy(
    btc_conf_file="/Users/will/Library/Application Support/Bitcoin/testnet3/bitcoin.conf")
refund_addr = proxy.getnewaddress("", "legacy")
address_details = submarine.get_address_details(address=refund_addr, network=NETWORK)

# setup swap object
swap = submarine.Swap(network=NETWORK, invoice=invoice['payreq'], refund=refund_addr)

# check the invoice is payable by the swap service
invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
# successful return implies that a possible route was found
assert invoice_details.status_code == 200
invoice_details_json = json.loads(invoice_details.text)

# create the swap request
swap.create()

# check swap was accepted
if swap.swap.status_code == 200:
    pass
else:
    print(swap.swap.status_code, swap.swap.text, swap.swap.reason)

# execute the swap payment
# check we have enough on-chain balance to pay the swap
on_chain_receipt = proxy.sendtoaddress(swap.swap_p2sh_address, (swap.swap_amount / SATOSHIS))
swap.tx_id = on_chain_receipt

# check the on-chain payment
if on_chain_receipt:
    print(f"On-chain swap payment complete, txid: {on_chain_receipt}")
else:
    print("On-chain swap payment using bitcoind failed")

swap.check_status()
swap_status = json.loads(swap.swap_status.text)
if swap_status['payment_secret']:
    print(f"Swap complete!\n"
          f"Swap secret: {swap_status['payment_secret']}\n"
          f"txid: {swap_status['transaction_id']}")
else:
    print(f"Waiting for 1 confirmation for txid: {on_chain_receipt}...")

    # get tx confirmations from bitcoind
    tx_status = proxy.gettransaction(f'{on_chain_receipt}')
    # check we've done things right
    assert tx_status['details'][0]['address'] == swap.swap_p2sh_address
    assert int(tx_status['details'][0]['amount'] * -1 * SATOSHIS)

    while proxy.gettransaction(f'{on_chain_receipt}')['confirmations'] < 1:
        sleep(10)
    print(f"Got 1 confirmation for on-chain payment txid: {on_chain_receipt}")

    # check the status of the swap
    swap.check_status()
    print("Waiting for swap approval...")
    elapsed = 0
    while proxy.gettransaction(f'{on_chain_receipt}')['confirmations'] <= 2:
        if not swap.swap_status.status_code == 200:
            sleep(30)
            elapsed += 30
            print(f"{elapsed}s")
            swap.check_status()
            print(f"Swap status: {swap.swap_status.text}")

    if swap.swap_status.status_code == 200:
        print(f"Swap approved: {swap.swap_status.text}")
    else:
        print(f"Swap not approved after 2 confirmations: {swap.swap_status.text}")
