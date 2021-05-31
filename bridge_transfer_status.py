"""
Show status all transfers on a token bridge
"""
from argparse import ArgumentParser
import csv
from dataclasses import dataclass, fields, asdict
from typing import List, Tuple

from eth_utils import to_hex
from web3.datastructures import AttributeDict

from utils import get_web3, get_events, load_abi, to_address, enable_logging


BRIDGES = {
    'rsk_eth_mainnet': {
        'rsk': {
            'bridge_address': '0x1ccad820b6d031b41c54f1f3da11c0d48b399581',
            'federation_address': '0x99896b7e917ff9c130bb86cde0d778be37e3464c',
            'bridge_start_block': 3373266,
            'chain': 'rsk_mainnet',
        },
        'other': {
            'bridge_address': '0x33c0d33a0d4312562ad622f91d12b0ac47366ee1',
            'federation_address': '0x2493b92b3b958c8d1e93899cae00bfc4854cbd18',
            'bridge_start_block': 12485023,
            'chain': 'eth_mainnet',
        }
    },
    'rsk_eth_testnet': {
        'rsk': {
            'bridge_address': '0xc0e7a7fff4aba5e7286d5d67dd016b719dcc9156',
            'federation_address': '0xd37b3876f4560cec6d8ef39ce4cb28ffd645b51a',
            'bridge_start_block': 1839957,
            'chain': 'rsk_testnet',
        },
        'other': {
            'bridge_address': '0x2b456e230225c4670fbf10b9da506c019a24cac7',
            'federation_address': '0x48a8f0efc6406674d4b3067ea49bda41f7ac2621',
            'bridge_start_block': 10222073,
            'chain': 'eth_testnet_ropsten',
        }
    }
}
BRIDGE_ABI = load_abi('token_bridge/Bridge')
FEDERATION_ABI = load_abi('token_bridge/Federation')


@dataclass
class Transfer:
    from_chain: str
    to_chain: str
    transaction_id: str
    was_processed: bool
    num_votes: int
    receiver_address: str
    token_address: str
    token_symbol: str
    amount_wei: int
    user_data: str
    event_block_number: int
    event_block_hash: str
    event_transaction_hash: str
    event_log_index: int
    #vote_transaction_args: Tuple
    #cross_event: AttributeDict


def main():
    parser = ArgumentParser(description="Show status of Cross events of bridge")
    parser.add_argument('bridge',
                        help='which bridge to use?',
                        choices=[
                            'rsk_eth_mainnet',
                            #'rsk_bsc_mainnet',  # TODO
                            'rsk_eth_testnet',
                            #'rsk_bsc_testnet'  # TODO
                        ])
    parser.add_argument('-o', '--outfile', help='Path of CSV file to write all transfers to', required=False)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    bridge_config = BRIDGES[args.bridge]
    print("Config:", args.bridge)

    if args.verbose:
        print("Verbose mode ON")
        enable_logging()

    print(f"CSV Output file: {args.outfile}")

    print("Transfers from RSK:")
    rsk_transfers = fetch_state(bridge_config['rsk'], bridge_config['other'])

    print("Transfers from the other chain:")
    other_transfers = fetch_state(bridge_config['other'], bridge_config['rsk'])

    print("Unprocessed transfers from RSK:")
    show_unprocessed_transfers(rsk_transfers)

    print("Unprocessed transfers from the other chain:")
    show_unprocessed_transfers(other_transfers)

    if args.outfile:
        print(f"Writing transfers in CSV form to {args.outfile}")
        with open(args.outfile, 'w', newline='') as csvfile:
            fieldnames = [f.name for f in fields(Transfer)]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for transfers in (rsk_transfers, other_transfers):
                for transfer in transfers:
                    writer.writerow(asdict(transfer))


def fetch_state(main_bridge_config, side_bridge_config) -> List[Transfer]:
    bridge_address = main_bridge_config['bridge_address']
    bridge_start_block = main_bridge_config['bridge_start_block']
    federation_address = side_bridge_config['federation_address']
    main_chain = main_bridge_config['chain']
    side_chain = side_bridge_config['chain']

    main_web3 = get_web3(main_chain)
    bridge_contract = main_web3.eth.contract(
        address=to_address(bridge_address),
        abi=BRIDGE_ABI,
    )
    bridge_end_block = main_web3.eth.get_block_number()

    side_web3 = get_web3(side_chain)
    federation_contract = side_web3.eth.contract(
        address=to_address(federation_address),
        abi=FEDERATION_ABI,
    )

    print(f'main: {main_chain}, side: {side_chain}, from: {bridge_start_block}, to: {bridge_end_block}')
    print('getting Cross events')
    cross_events = get_events(
        event=bridge_contract.events.Cross,
        from_block=bridge_start_block,
        to_block=bridge_end_block,
    )

    print(f'found {len(cross_events)} Cross events')
    transfers = []
    for event in cross_events:
        args = event.args
        vote_transaction_args = (
            args['_tokenAddress'],
            args['_to'],
            args['_amount'],
            args['_symbol'],
            event.blockHash,
            event.transactionHash,
            event.logIndex,
            args['_decimals'],
            args['_granularity'],
        )
        print(event)
        transaction_id = federation_contract.functions.getTransactionId(*vote_transaction_args).call()
        transaction_id = to_hex(transaction_id)
        print('transaction_id', transaction_id)
        num_votes = federation_contract.functions.getTransactionCount(transaction_id).call()
        print('num_votes', num_votes)
        was_processed = federation_contract.functions.transactionWasProcessed(transaction_id).call()
        print('was_processed', was_processed)
        transfer = Transfer(
            from_chain=main_chain,
            to_chain=side_chain,
            transaction_id=transaction_id,
            num_votes=num_votes,
            was_processed=was_processed,
            token_symbol=args['_symbol'],
            receiver_address=args['_to'],
            token_address=args['_tokenAddress'],
            amount_wei=args['_amount'],
            user_data=to_hex(args['_userData']),
            event_block_number=event.blockNumber,
            event_block_hash=event.blockHash.hex(),
            event_transaction_hash=event.transactionHash.hex(),
            event_log_index=event.logIndex,
            #vote_transaction_args=vote_transaction_args,
            #cross_event=event,
        )
        transfers.append(transfer)
    return transfers


def show_unprocessed_transfers(transfers: List[Transfer]):
    unprocessed_transfers = [t for t in transfers if not t.was_processed]
    for transfer in unprocessed_transfers:
        print(transfer)


if __name__ == '__main__':
    main()
