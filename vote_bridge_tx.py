from argparse import ArgumentParser
from getpass import getpass
from typing import Callable, Iterable, Optional, TypeVar

from eth_account import Account
from eth_utils import is_hex, to_hex
from web3.logs import DISCARD
from web3.middleware import geth_poa_middleware

from constants import BRIDGES, BRIDGE_ABI, FEDERATION_ABI
from utils import get_web3, set_web3_account, to_address

T = TypeVar('T')


def main():
    parser = ArgumentParser(description="Get status and/or vote for a transaction")
    parser.add_argument('--bridge',
                        help='which bridge to use?',
                        choices=list(BRIDGES.keys()),
                        default=None),
    parser.add_argument('--deposit-chain',
                        help='chain of deposit',
                        choices=['rsk', 'other', 'eth', 'bsc'],
                        default=None)
    parser.add_argument('--tx-hash',
                        help='deposit transaction hash',
                        default=None)
    parser.add_argument('--private-key',
                        help='federator account private key',
                        default=None)
    args = parser.parse_args()

    if args.bridge:
        bridge_name = args.bridge
    else:
        bridge_name = prompt_option(
            options=BRIDGES.keys(),
            prompt='Select bridge:'
        )

    side_chain_name = bridge_name.split('_')[1]

    if args.deposit_chain:
        if args.deposit_chain == 'rsk':
            chain_name = 'rsk'
        elif args.deposit_chain_name in ('other', side_chain_name):
            chain_name = side_chain_name
        else:
            raise ValueError(f"invalid chain name: {args.deposit_chain}")
    else:
        chain_name = prompt_option(
            options=['rsk', side_chain_name],
            prompt='Select side of deposit:'
        )

    if chain_name == 'rsk':
        bridge_config = BRIDGES[bridge_name]['rsk']
        side_bridge_config = BRIDGES[bridge_name]['other']
    else:
        bridge_config = BRIDGES[bridge_name]['other']
        side_bridge_config = BRIDGES[bridge_name]['rsk']
        side_chain_name = 'rsk'

    #print("Bridge config:")
    #pprint(bridge_config)
    bridge_address = bridge_config['bridge_address']
    federation_address = side_bridge_config['federation_address']
    print("Bridge address:", bridge_address, f'({chain_name})')
    print("Federation address:", bridge_address, f'({side_chain_name})')

    web3 = get_web3(bridge_config['chain'])
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)  # TODO: is this really required?
    side_web3 = get_web3(side_bridge_config['chain'])
    side_web3.middleware_onion.inject(geth_poa_middleware, layer=0)  # TODO: is this really required?
    bridge_contract = web3.eth.contract(
        address=to_address(bridge_address),
        abi=BRIDGE_ABI,
    )
    federation_contract = side_web3.eth.contract(
        address=to_address(federation_address),
        abi=FEDERATION_ABI,
    )

    if args.tx_hash:
        tx_hash = args.tx_hash
        if get_tx_hash_error(tx_hash):
            raise ValueError(get_tx_hash_error(tx_hash))
    else:
        tx_hash = prompt_validated(
            prompt='Input transaction hash:',
            get_error=get_tx_hash_error,
        )

    print('Fetching receipt for transaction', tx_hash)
    tx_receipt = web3.eth.get_transaction_receipt(tx_hash)

    print('Got transaction receipt, parsing Cross events')
    cross_events = bridge_contract.events.Cross().processReceipt(
        tx_receipt,
        errors=DISCARD
    )

    if len(cross_events) == 0:
        print(f"Error: No Cross events found for transaction {tx_hash} on bridge {bridge_name} ({chain_name})")
        return False
    if len(cross_events) == 1:
        cross_event = cross_events[0]
    else:
        print("Got multiple Cross events (shouldn't happen...)")
        cross_event = prompt_option(
            options=cross_events,
            prompt='Select wanted Cross event'
        )

    print("Cross event:")
    print(cross_event)

    if cross_event.address.lower() != bridge_address.lower():
        print(
            f"ERROR! Cross event address {cross_event.address} differs from given bridge address {bridge_address} "
            f"({bridge_name}, {chain_name})")
        print("Run the script again and select the correct bridge network")
        return False

    print(f"Getting transactionId from federation contract {federation_address} ({side_chain_name})")
    # TODO: in the future, use getTransactionIdU
    vote_transaction_args = (
        cross_event.args['_tokenAddress'],
        cross_event.args['_to'],
        cross_event.args['_amount'],
        cross_event.args['_symbol'],
        cross_event.blockHash,
        cross_event.transactionHash,
        cross_event.logIndex,
        cross_event.args['_decimals'],
        cross_event.args['_granularity'],
    )
    vote_transaction_args_with_userdata = vote_transaction_args + (
        cross_event.args['_userData'],
    )
    transaction_id = federation_contract.functions.getTransactionId(*vote_transaction_args).call()
    transaction_id = to_hex(transaction_id)
    print(f"transactionId: {transaction_id}")
    transaction_id_u = federation_contract.functions.getTransactionIdU(*vote_transaction_args_with_userdata).call()
    transaction_id_u = to_hex(transaction_id_u)
    print(f"transactionIdU: {transaction_id_u}")

    print("Fetching transaction data...")
    num_votes = federation_contract.functions.getTransactionCount(transaction_id).call()
    num_votes_u = federation_contract.functions.getTransactionCount(transaction_id_u).call()
    print("Num votes:", num_votes)
    print("Num votes (U):", num_votes_u)
    was_processed = federation_contract.functions.transactionWasProcessed(transaction_id).call()
    was_processed_u = federation_contract.functions.transactionWasProcessed(transaction_id_u).call()
    print("Was processed:", was_processed)
    print("Was processed (U):", was_processed_u)

    if was_processed or was_processed_u:
        print("Transaction already processed")
        return

    if args.private_key:
        private_key = args.private_key
    else:
        private_key = getpass("Enter federator private key (input hidden): ")
    account = Account.from_key(private_key)
    print("Account:", account.address)

    set_web3_account(
        web3=web3,
        account=account,
    )
    set_web3_account(
        web3=side_web3,
        account=account,
    )

    is_member = federation_contract.functions.isMember(account.address).call()
    print("Is federation member:", is_member)
    has_voted = federation_contract.functions.votes(transaction_id, account.address).call()
    print("Has voted:", has_voted)
    has_voted_u = federation_contract.functions.votes(transaction_id_u, account.address).call()
    print("Has voted (U):", has_voted_u)

    if not is_member:
        print(f"Error: Account {account.address} is not a federator and cannot vote.")
        return
    if has_voted or has_voted_u:
        print(f"Account {account.address} has already voted for {transaction_id}.")
        return

    vote_input = input("Vote for transaction? [y/n] ")
    do_vote = vote_input and len(vote_input) > 0 and vote_input[0].lower() == 'y'
    if not do_vote:
        print("Not voting -- quitting!")
        return

    print("Voting for transaction.")
    vote_tx_hash = federation_contract.functions.voteTransaction(*vote_transaction_args).transact()
    vote_tx_hash = to_hex(vote_tx_hash)
    print("Vote tx:", vote_tx_hash)
    print("Waiting for receipt")
    side_web3.eth.wait_for_transaction_receipt(vote_tx_hash)
    print("All done.")


def prompt_option(options: Iterable[T], *, prompt: str = 'Select option:') -> T:
    options = list(options)
    ret = None
    while True:
        print(prompt)
        for i, option in enumerate(options, start=1):
            print(f"{i}) {option}")
        selected = input()
        if selected.isdigit():
            index = int(selected) - 1
            if 0 <= index < len(options):
                ret = options[index]
                break
        print(f"Invalid option: {selected!r}")
    print(f"Selected: {ret!r}")
    return ret


def prompt_validated(*, get_error: Callable[[str], Optional[str]], prompt: str) -> str:
    while True:
        data = input(f'{prompt} ')
        error = get_error(data)
        if error is None:
            return data
        else:
            print("Error:", error)


def get_tx_hash_error(s: str) -> Optional[str]:
    if is_hex(s) and len(s) == 66:
        return None
    return f'Not a valid tx hash: {s!r}'


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Cancelled!")
