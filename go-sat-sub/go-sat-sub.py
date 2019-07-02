import json

from secrets import token_hex
from time import sleep

import lnd_grpc

from blocksat_api import blocksat
from submarine_api import submarine

NETWORK = 'testnet'

# setup lnd testnet client
lnd = lnd_grpc.Client(network=NETWORK)

# create random 64 byte message to be sent
message = token_hex(64)

# setup the satellite Order
sat = blocksat.Order(message=message, network=NETWORK)
# note bid is in milli-satoshis
bid_msat = sat.size * 50
sat.place(bid=bid_msat)
if sat.api_status_code == 200:
    pass
else:
    while not sat.api_status_code == 200:
        bid_msat = bid_msat + 10
        sat.place(bid=bid_msat)
        sleep(2)
invoice = sat.place_response['lightning_invoice']

# check we have available off-chain funds to send
# not strictly really as submarine will pay our invoice for us
channel_balance = lnd.channel_balance().balance
# account for 1% channel reserve with extra 2%
assert channel_balance > ((bid_msat / 1000) * 1.02)

# change refund address for mainnet -- need access to privkey for refunds!!
refund_addr = lnd.new_address('p2wkh').address

# setup swap object
swap = submarine.Swap(network=NETWORK, invoice=invoice['payreq'], refund=refund_addr)

# check the invoice is payable by the swap service
invoice_details = submarine.get_invoice_details(network=NETWORK, invoice=invoice['payreq'])
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
assert lnd.wallet_balance().confirmed_balance > swap.swap_amount
on_chain_receipt = lnd.send_coins(addr=swap.swap_p2sh_address,
                                  amount=swap.swap_amount,
                                  target_conf=1)

# check the on-chain payment
if on_chain_receipt.txid:
    pass
else:
    print("On-chain payment using LND failed")

print(f"Waiting for a confirmation for transaction {on_chain_receipt.txid}")
# setup thread to monitor for on-chain tx confirmation for the swap tx
for transaction in lnd.subscribe_transactions():
    # tx_queue.put(transaction)
    print(transaction)
    # if the transaction matches, break the thread
    if transaction.tx_hash == on_chain_receipt.txid:
        print(f"Txid {on_chain_receipt.txid} has 1 confirmation on the blockchain")
        break

# check the status of the swap
swap.check_status()
print("Waiting for swap approval...")
elapsed = 0
while lnd.get_transactions().transactions[-1].num_confirmations <= 2:
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
