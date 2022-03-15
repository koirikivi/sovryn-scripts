import dataclasses
import enum
import os
import sys
import time
from collections import defaultdict
from pprint import pprint
from typing import Optional

from eth_account import Account
from eth_utils import to_hex
from eth_abi import encode_abi
from web3.logs import DISCARD

from utils import get_erc20_contract, get_events, get_web3, load_abi, set_web3_account, to_address, enable_logging

enable_logging()

try:
    command = sys.argv[1]
except IndexError:
    command = None

print("Command:", command)
test_account_private_key = os.environ['TEST_ACCOUNT_PRIVATE_KEY']
test_account = Account.from_key(test_account_private_key)

fastbtc_inbox_address = "0x745a3629D7AFCf53caf96b6350105F16bA2350Bf"
#fastbtc_bridge_address = "0x53b202E87Eb5F60a9779c4Dcae14c1037D2C0422"  # old fastbtc
#fastbtc_bridge_deploy_block = 2326996
fastbtc_bridge_address = "0x10C848e9495a32acA95F6c23C92eCA2b2bE9903A"  # new fastbtc
fastbtc_bridge_deploy_block = 2417524

rsk_allow_tokens_address = '0xa9f2ccb27fe01479a1f21f3a236989c614f801bc'
#rsk_wrbtc_token_address = to_address('0x69fe5cec81d5ef92600c1a0db1f11986ab3758ab')
rsk_rbtc_wrapper_address = to_address('0xf629e5c7527ac7bc9ce26bdd6d66f0eb955ef3b2')
rsk_bridge_address = to_address('0x2b2bcad081fa773dc655361d1bb30577caa556f8')
rsk_federation_address = to_address('0x07081144a97b58f08AB8bAaf8b05D87f5d31e5dF')
rsk_old_managed_wallet_address = to_address('0xcC099752238b1932587bf5793Afeb7d80D04F6e1')
rsk_new_managed_wallet_address = to_address('0x8dC7B212692b3E36aF7E8202F06516d0dB3Bf1B6')

bsc_btcs_aggregator_address = '0xe2C2fbAa4407fa8BB0Dbb7a6a32aD36f8bA484aE'
bsc_btcs_token_address = "0x0ed2a1edde92b25448db95e5aa9fe9e9bc0193bf"
bsc_brbtc_token_address = to_address("0xc41d41cb7a31c80662ac2d8ab7a7e5f5841eebc3")

bsc_to_btc_transfer_amount_wei = 20000000000000
#bitcoin_address = "tb1qls9xn6hjvjtnj3exw0nwqee894qfx2kp6hvm32"  # old
#bitcoin_address = "tb1qlzy4feg900aklfahrcchuufxul6wf06d3mg97s"  # new
bitcoin_address = "mxYAM6oLjjEMesiL5A3EMU6iDMd8kyQdfR"

rsk_to_bsc_transfer_amount_wei = 200000000000000
rsk_to_bsc_transfer_amount_dec = '0.000200000000000000'

bsc_web3 = get_web3('bsc_testnet', account=test_account)
rsk_web3 = get_web3('rsk_testnet', account=test_account)


rsk_bridge = rsk_web3.eth.contract(
    address=rsk_bridge_address,
    abi=load_abi('token_bridge/Bridge'),
)
rsk_federation = rsk_web3.eth.contract(
    address=rsk_federation_address,
    abi=load_abi('token_bridge/Federation'),
)
rsk_allowtokens = rsk_web3.eth.contract(
    address=to_address(rsk_allow_tokens_address),
    abi=load_abi('token_bridge/AllowTokens'),
)

fastbtc_inbox = rsk_web3.eth.contract(
    address=to_address(fastbtc_inbox_address),
    abi=load_abi('bidirectional-fastbtc/FastBTCInbox'),
)
fastbtc_bridge = rsk_web3.eth.contract(
    address=to_address(fastbtc_bridge_address),
    abi=load_abi('bidirectional-fastbtc/FastBTCBridge'),
)
inbox_wrbtc_address = fastbtc_inbox.functions.wrbtcToken().call()
print("Inbox WRBTC   ", inbox_wrbtc_address)
print("Expected WRBTC", rsk_rbtc_wrapper_address)
if inbox_wrbtc_address.lower() != rsk_rbtc_wrapper_address.lower():
    print(f"WARNING! inbox doesn't have the expected WRBTC address {rsk_rbtc_wrapper_address}")

bsc_aggregator = bsc_web3.eth.contract(
    address=to_address(bsc_btcs_aggregator_address),
    abi=load_abi('babelfish/MassetV3'),
)
print("Aggregator version", bsc_aggregator.functions.getVersion().call())
assert bsc_aggregator.functions.getToken().call().lower() == bsc_btcs_token_address.lower()

bsc_btcs = get_erc20_contract(
    token_address=to_address(bsc_btcs_token_address),
    web3=bsc_web3
)
print("rsk address    ", test_account.address)
print("bitcoin address", bitcoin_address)

if command == 'transfer_from_bsc_to_btc':
    transfer_fee = rsk_allowtokens.functions.getFeePerToken(rsk_rbtc_wrapper_address).call()
    print("Fee:", transfer_fee)
    min_per_token = rsk_allowtokens.functions.getMinPerToken(rsk_rbtc_wrapper_address).call()
    print("Min per token:", min_per_token)
    min_transfer_satoshi = fastbtc_bridge.functions.minTransferSatoshi().call()
    satoshi_divisor = fastbtc_bridge.functions.SATOSHI_DIVISOR().call()
    min_transfer_wei = min_transfer_satoshi * satoshi_divisor
    if bsc_to_btc_transfer_amount_wei - transfer_fee < min_transfer_wei:
        raise ValueError(
            f"transfer amount {min_transfer_wei} minus fee {transfer_fee} "
            f"({min_transfer_wei - transfer_fee}) is less than min amount {min_transfer_wei}"
        )
    print("Min transfer:", min_transfer_satoshi, "satoshi,", min_transfer_wei, "wei")

    print("BTCs balance   ", bsc_btcs.functions.balanceOf(test_account.address).call())
    print("Transfer amount", bsc_to_btc_transfer_amount_wei)

    #user_data = fastbtc_inbox.functions.encodeUserData(test_account.address, bitcoin_address).call()
    user_data = fastbtc_bridge.functions.encodeBridgeUserData(test_account.address, bitcoin_address).call()
    print("User data      ", to_hex(user_data))

    if bsc_btcs.functions.allowance(test_account.address, bsc_btcs_aggregator_address).call() < bsc_to_btc_transfer_amount_wei:
        print("Setting allowance")
        tx = bsc_btcs.functions.approve(bsc_btcs_aggregator_address, 2**256 - 1).transact()
        print("Done, tx:", to_hex(tx), "waiting for receipt")
        bsc_web3.eth.wait_for_transaction_receipt(tx)

    print("Redeeming to bridge in 3s...")
    time.sleep(3)

    #"0xc41d41cb7a31c80662ac2d8ab7a7e5f5841eebc3","20000000000000","0x18a2EF981110C23Cf1a58065EfA41b27AD963980","0x000000000000000000000000a7a7a7"
    tx = bsc_aggregator.functions.redeemToBridge(
        bsc_brbtc_token_address,
        bsc_to_btc_transfer_amount_wei,
        #fastbtc_inbox_address,
        fastbtc_bridge_address,
        #test_account.address,
        user_data,
    ).transact()
    print("Done, tx:", to_hex(tx), "waiting for receipt")
    bsc_web3.eth.wait_for_transaction_receipt(tx)
elif command == 'transfer_from_rsk_to_bsc':
    print("RBTC balance (RSK)          ", rsk_web3.eth.get_balance(test_account.address))
    print("BTCs balance (BSC)          ", bsc_btcs.functions.balanceOf(test_account.address).call())
    print("Transfer amount (RSK to BSC)", rsk_to_bsc_transfer_amount_wei)

    encoded_address = encode_abi(['address'], [test_account.address])
    print("Address:        ", test_account.address)
    print("Encoded address:", to_hex(encoded_address))

    print("Transferring RBTC through RSK bridge to BSC in 3s...")
    time.sleep(3)

    tx = rsk_bridge.functions.receiveEthAt(
        bsc_btcs_aggregator_address,
        encoded_address
    ).transact({
        "value": rsk_to_bsc_transfer_amount_wei
    })
    print("Done, tx:", to_hex(tx), "waiting for receipt")
    rsk_web3.eth.wait_for_transaction_receipt(tx)

elif command == 'accept_transfers':
    # TODO: no longer in use
    to_block = rsk_web3.eth.get_block_number()
    inbox_received_events = get_events(
       event=fastbtc_inbox.events.Received(),
       from_block=2_360_000,
       to_block=to_block,
       batch_size=10_000
    )
    print("Found", len(inbox_received_events), "inbox transfers")
    pprint(inbox_received_events)

    acceptable_transfers = []
    for i, event in enumerate(inbox_received_events, start=1):
        tx_hash = event.transactionHash
        print(f"Event #{i}, block: {event.blockNumber}, tx: {to_hex(tx_hash)}")
        receipt = rsk_web3.eth.get_transaction_receipt(tx_hash)
        voted_events = rsk_federation.events.Voted().processReceipt(
            receipt,
            errors=DISCARD
        )
        executed_events = rsk_federation.events.Executed().processReceipt(
            receipt,
            errors=DISCARD
        )
        print(len(voted_events), "voted events")
        print(len(executed_events), "executed events")
        executed_transaction_ids = set(e.args.transactionId for e in executed_events)
        for voted_event in voted_events:
            transaction_id = voted_event.args.transactionId
            if transaction_id not in executed_transaction_ids:
                print(f"Event with tx id u {to_hex(transaction_id)} voted but not executed")
                continue
            if fastbtc_inbox.functions.acceptedTokenBridgeTransfers(transaction_id).call():
                print(f"Event with tx id u {to_hex(transaction_id)} already accepted")
                continue
            acceptable_transfers.append(
                (
                    voted_event.args.amount,
                    voted_event.args.symbol,
                    voted_event.args.blockHash,
                    voted_event.args.transactionHash,
                    voted_event.args.logIndex,
                    voted_event.args.decimals,
                    voted_event.args.granularity,
                    voted_event.args.userData
                )
            )

    if acceptable_transfers:
        print("Accepting", len(acceptable_transfers), "transfers")
        time.sleep(3)
    else:
        print("No transfers to accept")
    for i, args in enumerate(acceptable_transfers, start=1):
        print(
            f"Accepting event #{i} with args:", args
        )
        tx = fastbtc_inbox.functions.acceptTokenBridgeTransfer(*args).transact()
        print("Done, tx:", to_hex(tx), "waiting for receipt")
        rsk_web3.eth.wait_for_transaction_receipt(tx)

    #accepted_cross_transfer_events = get_events(
    #    event=rsk_bridge.events.AcceptedCrossTransfer(),
    #    argument_filters=dict(
    #        _to=fastbtc_inbox_address
    #    ),
    #    from_block=2_300_000,
    #    to_block=to_block,
    #    batch_size=10_000
    #)
    #print("Found", len(accepted_cross_transfer_events), "inbox transfers")
    #pprint(accepted_cross_transfer_events)


elif command == 'accept_bridge_transfer':
    try:
        _, _, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData = sys.argv
    except ValueError:
        sys.exit(
            "Not enough arguments given. Expected: amount, symbol, blockHash, transactionHash, logIndex, decimals, "
            "granularity, userData"
        )
    amount = int(amount)
    logIndex = int(logIndex)
    decimals = int(decimals)
    granularity = int(granularity)

    transaction_id_u = rsk_federation.functions.getTransactionIdU(
        rsk_rbtc_wrapper_address,
        fastbtc_inbox_address,
        amount,
        symbol,
        blockHash,
        transactionHash,
        logIndex,
        decimals,
        granularity,
        userData
    ).call()
    print("transaction_id_u", to_hex(transaction_id_u))
    print("processed by federation?", rsk_federation.functions.processed(transaction_id_u).call())
    print(
        "processed by bridge?",
        rsk_bridge.functions.processed(
            rsk_bridge.functions.getTransactionId(
                blockHash,
                transactionHash,
                fastbtc_inbox_address,
                amount,
                logIndex
            ).call()
        ).call()
    )

    print(
        "Accepting in 3s with args:",
        amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData
    )
    time.sleep(3)

    tx = fastbtc_inbox.functions.acceptTokenBridgeTransfer(
        amount,
        symbol,
        blockHash,
        transactionHash,
        logIndex,
        decimals,
        granularity,
        userData
    ).transact()
    print("Done, tx:", to_hex(tx), "waiting for receipt")
    rsk_web3.eth.wait_for_transaction_receipt(tx)
elif command == "get_transfer_history":
    from_block = fastbtc_bridge_deploy_block
    to_block = rsk_web3.eth.get_block_number()
    user_address = ''
    try:
        user_address = sys.argv[2]
        print("Showing transfers from user", user_address)
    except IndexError:
        print("Showing transfers from all users")

    class TransferStatus(enum.IntEnum):
        NOT_APPLICABLE = 0
        NEW = 1
        SENDING = 2
        MINED = 3
        REFUNDED = 4

    @dataclasses.dataclass()
    class BitcoinTransfer:
        transfer_id: str
        rsk_address: str
        bitcoin_address: str
        total_amount_satoshi: int
        net_amount_satoshi: int
        fee_satoshi: int
        #is_bridge_transfer: bool
        status: TransferStatus
        bitcoin_tx_id: Optional[str] = None


    # TODO: this can be optimized at least by reducing the amount of calls needed,
    # and by utilizing filters better
    new_bitcoin_transfer_events = get_events(
        event=fastbtc_bridge.events.NewBitcoinTransfer(),
        from_block=from_block,
        to_block=to_block,
        batch_size=10_000,
        # Cannot filter by rskAddress if we take FastBTCInbox NewTokenBridgeBitcoinTransfer events into account
        argument_filters=dict(
            rskAddress=user_address,
        ) if user_address else None
    )
    print("Found", len(new_bitcoin_transfer_events), "NewBitcoinTransfer events")

    #new_token_bridge_bitcoin_transfer_events = get_events(
    #    event=fastbtc_inbox.events.NewTokenBridgeBitcoinTransfer(),
    #    from_block=from_block,
    #    to_block=to_block,
    #    batch_size=10_000,
    #    argument_filters=dict(
    #        rskAddress=user_address,
    #    ) if user_address else None
    #)
    #print("Found", len(new_bitcoin_transfer_events), "NewTokenBridgeBitcoinTransfer events")

    bitcoin_transfer_batch_sending_events = get_events(
        event=fastbtc_bridge.events.BitcoinTransferBatchSending(),
        from_block=from_block,
        to_block=to_block,
        batch_size=10_000,
    )
    print("Found", len(bitcoin_transfer_batch_sending_events), "BitcoinTransferBatchSending events")

    bitcoin_transfer_status_updated_events = get_events(
        event=fastbtc_bridge.events.BitcoinTransferStatusUpdated(),
        from_block=from_block,
        to_block=to_block,
        batch_size=10_000,
    )
    print("Found", len(bitcoin_transfer_batch_sending_events), "BitcoinTransferStatusUpdated events")

    transfer_batch_sending_events_by_tx_hash = defaultdict(list)
    for event in bitcoin_transfer_batch_sending_events:
        # Add a reference to this event for each event in the transferBatchSize,
        # to make processing easier
        transfer_batch_sending_events_by_tx_hash[event.transactionHash].extend(
            [event] * event.args.transferBatchSize
        )

    bitcoin_tx_ids_by_transfer_id = dict()
    statuses_by_transfer_id = dict()
    #actual_rsk_addresses_by_transfer_id = dict()

    #for event in new_token_bridge_bitcoin_transfer_events:
    #    actual_rsk_addresses_by_transfer_id[event.args.transferId] = event.args.rskAddress

    for event in bitcoin_transfer_status_updated_events:
        status = TransferStatus(event.args.newStatus)
        statuses_by_transfer_id[event.args.transferId] = status
        if status == TransferStatus.SENDING:
            sending_event = transfer_batch_sending_events_by_tx_hash[event.transactionHash].pop(0)
            bitcoin_tx_ids_by_transfer_id[event.args.transferId] = sending_event.args.bitcoinTxHash

    transfers = []
    for event in new_bitcoin_transfer_events:
        bitcoin_tx_id = bitcoin_tx_ids_by_transfer_id.get(event.args.transferId)
        if bitcoin_tx_id:
            bitcoin_tx_id = to_hex(bitcoin_tx_id)[2:]

        #rsk_address = actual_rsk_addresses_by_transfer_id.get(event.args.transferId, event.args.rskAddress)
        rsk_address = event.args.rskAddress
        if user_address and rsk_address.lower() != user_address.lower():
            continue
        transfer = BitcoinTransfer(
            transfer_id=to_hex(event.args.transferId),
            rsk_address=rsk_address,
            bitcoin_address=event.args.btcAddress,
            total_amount_satoshi=event.args.amountSatoshi + event.args.feeSatoshi,
            net_amount_satoshi=event.args.amountSatoshi,
            fee_satoshi=event.args.feeSatoshi,
            #is_bridge_transfer=event.args.transferId in actual_rsk_addresses_by_transfer_id,
            status=statuses_by_transfer_id.get(event.args.transferId, TransferStatus.NEW),
            bitcoin_tx_id=bitcoin_tx_id,
        )
        transfers.append(transfer)

    for transfer in transfers:
        print(transfer)

elif command == "set_wrbtc_address":
    admin_account_private_key = os.getenv('ADMIN_PRIVATE_KEY')
    if not admin_account_private_key:
        sys.exit("provide env var ADMIN_PRIVATE_KEY")
    set_web3_account(
        web3=rsk_web3,
        account=Account.from_key(admin_account_private_key)
    )

    print("Setting WRBTC to", rsk_rbtc_wrapper_address)
    time.sleep(3)
    tx = fastbtc_inbox.functions.setWrbtcToken(
        rsk_rbtc_wrapper_address
    ).transact()

    print("Done, tx:", to_hex(tx), "waiting for receipt")
    rsk_web3.eth.wait_for_transaction_receipt(tx)
elif command == 'check_managed_wallet':
    old_managed_wallet = rsk_web3.eth.contract(
        address=rsk_old_managed_wallet_address,
        abi=load_abi('fastbtc/ManagedWallet'),
    )
    print("Old ManagedWallet at", rsk_old_managed_wallet_address)
    old_admin = old_managed_wallet.functions.admin().call()
    print("Admin:", old_admin)
    print("Owner:", old_managed_wallet.functions.owner().call())
    new_managed_wallet = rsk_web3.eth.contract(
        address=rsk_new_managed_wallet_address,
        abi=load_abi('fastbtc/ManagedWallet'),
    )
    print("New ManagedWallet at", rsk_new_managed_wallet_address)
    previous_new_admin = new_managed_wallet.functions.admin().call()
    print("Admin:", previous_new_admin)
    print("Owner:", new_managed_wallet.functions.owner().call())
    print("Old balance: ", rsk_web3.eth.get_balance(old_managed_wallet.address))
    new_balance = rsk_web3.eth.get_balance(new_managed_wallet.address)
    print("New balance: ", new_balance)
    print("User balance:", rsk_web3.eth.get_balance(test_account.address))
    if old_admin != previous_new_admin:
        print("Setting new ManagedWallet admin to", old_admin, "in 3s")
        time.sleep(3)
        tx = new_managed_wallet.functions.changeAdmin(old_admin).transact()
        print("Tx:", to_hex(tx))
    goal_balance = int(0.25 * 10**18)
    if new_balance < goal_balance / 2:
        print("Funding the wallet in 3s")
        time.sleep(3)
        tx = rsk_web3.eth.send_transaction({
            "to": rsk_new_managed_wallet_address,
            "value": goal_balance
        })
        print("Tx:", to_hex(tx))

elif command == 'pending_tx_fix':
    a = rsk_web3.eth.get_transaction_count(test_account.address, block_identifier='latest')
    print("Latest", a)
    b = rsk_web3.eth.get_transaction_count(test_account.address, block_identifier='pending')
    print("Pending", b)
    goal_nonce = 22
    nonce = a
    while nonce <= goal_nonce:
        tx_hash = rsk_web3.eth.send_transaction({
            "to": test_account.address,
            "value": bsc_to_btc_transfer_amount_wei,
            "nonce": nonce
        })
        print("Nonce:", nonce, "tx", to_hex(tx_hash))
        nonce += 1

elif command == "check_bridge_receiver":
    try:
        _, _, address = sys.argv
    except ValueError:
        sys.exit(
            "Not enough arguments given. Expected: address"
        )
    print(
        f"Is {address} a bridge receiver for {rsk_bridge.address}?",
        "Yes!" if rsk_bridge.functions.isBridgeReceiver(address).call() else "NO!"
    )

else:
    if command:
        print("Unknown command:", command)
    else:
        print("Stopping here because no command given")
