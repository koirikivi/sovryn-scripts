"""
Show status all transfers on a token bridge
"""
import csv
from argparse import ArgumentParser
from dataclasses import asdict, dataclass, fields
from typing import List, Optional

from eth_utils import to_hex
from web3.logs import DISCARD

from constants import BRIDGES, BRIDGE_ABI, FEDERATION_ABI
from utils import enable_logging, get_events, get_web3, to_address


@dataclass
class Transfer:
    from_chain: str
    to_chain: str
    transaction_id: str
    transaction_id_old: str
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
    executed_transaction_hash: str
    executed_block_hash: str
    executed_block_number: int
    executed_log_index: int
    has_error_token_receiver_events: bool
    error_data: str
    #vote_transaction_args: Tuple
    #cross_event: AttributeDict


def main():
    parser = ArgumentParser(description="Show status of Cross events of bridge")
    parser.add_argument('bridge',
                        help='which bridge to use?',
                        choices=list(BRIDGES.keys())),
    parser.add_argument('-o', '--outfile', help='Path of CSV file to write all transfers to', required=False)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    parser.add_argument('--rsk-start-block', type=int, default=None)
    parser.add_argument('--other-start-block', type=int, default=None)
    args = parser.parse_args()

    bridge_config = BRIDGES[args.bridge]
    print("Config:", args.bridge)

    if args.verbose:
        print("Verbose mode ON")
        enable_logging()

    print(f"CSV Output file: {args.outfile}")

    print("Transfers from RSK:")
    rsk_transfers = fetch_state(bridge_config['rsk'],
                                bridge_config['other'],
                                bridge_start_block=args.rsk_start_block,
                                federation_start_block=args.other_start_block)

    print("Transfers from the other chain:")
    other_transfers = fetch_state(bridge_config['other'],
                                  bridge_config['rsk'],
                                  bridge_start_block=args.other_start_block,
                                  federation_start_block=args.rsk_start_block)

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


def fetch_state(main_bridge_config, side_bridge_config, *,
                bridge_start_block: Optional[int] = None,
                federation_start_block: Optional[int] = None) -> List[Transfer]:
    bridge_address = main_bridge_config['bridge_address']
    if not bridge_start_block:
        bridge_start_block = main_bridge_config['bridge_start_block']
    if not federation_start_block:
        federation_start_block = side_bridge_config['bridge_start_block']
    side_bridge_address = side_bridge_config['bridge_address']
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
    federation_end_block = side_web3.eth.get_block_number()
    side_bridge_contract = side_web3.eth.contract(
        address=to_address(side_bridge_address),
        abi=BRIDGE_ABI,
    )

    print(f'main: {main_chain}, side: {side_chain}, from: {bridge_start_block}, to: {bridge_end_block}')
    print('getting Cross events')
    cross_events = get_events(
        event=bridge_contract.events.Cross,
        from_block=bridge_start_block,
        to_block=bridge_end_block,
    )
    print(f'found {len(cross_events)} Cross events')

    print('getting Executed events')
    executed_events = get_events(
        event=federation_contract.events.Executed,
        from_block=federation_start_block,
        to_block=federation_end_block,
    )
    print(f'found {len(executed_events)} Executed events')
    executed_event_by_transaction_id = {
        to_hex(e.args.transactionId): e
        for e in executed_events
    }

    print('processing transfers')
    transfers = []
    for event in cross_events:
        args = event.args
        tx_id_args_old = (
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
        tx_id_args = tx_id_args_old + (
            args['_userData'],
        )
        print(event)
        transaction_id = federation_contract.functions.getTransactionIdU(*tx_id_args).call()
        transaction_id = to_hex(transaction_id)
        print('transaction_id', transaction_id)
        transaction_id_old = federation_contract.functions.getTransactionId(*tx_id_args_old).call()
        transaction_id_old = to_hex(transaction_id_old)
        print('transaction_id_old', transaction_id_old)
        num_votes = federation_contract.functions.getTransactionCount(transaction_id).call()
        print('num_votes', num_votes)
        was_processed = federation_contract.functions.transactionWasProcessed(transaction_id).call()
        print('was_processed', was_processed)
        executed_event = executed_event_by_transaction_id.get(transaction_id)
        print('related Executed event', executed_event)
        executed_transaction_hash = executed_event.transactionHash.hex() if executed_event else None
        error_token_receiver_events = tuple()
        if executed_transaction_hash:
            receipt = side_web3.eth.get_transaction_receipt(executed_transaction_hash)
            error_token_receiver_events = side_bridge_contract.events.ErrorTokenReceiver().processReceipt(
                receipt,
                errors=DISCARD,  # TODO: is this right?
            )

        transfer = Transfer(
            from_chain=main_chain,
            to_chain=side_chain,
            transaction_id=transaction_id,
            transaction_id_old=transaction_id_old,
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
            executed_transaction_hash=executed_transaction_hash,
            executed_block_hash=executed_event.blockHash.hex() if executed_event else None,
            executed_block_number=executed_event.blockNumber if executed_event else None,
            executed_log_index=executed_event.logIndex if executed_event else None,
            has_error_token_receiver_events=bool(error_token_receiver_events),
            error_data=to_hex(error_token_receiver_events[0].args._errorData) if error_token_receiver_events else '0x',
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
