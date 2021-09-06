#!/usr/bin/env python3
"""
Check for inconsistencies in logs returned by eth_getLogs and eth_getTransactionReceipt

- Check that the `data` field is the same for logs with same transactionHash and logIndex,
  between JSONRPC responses from eth_getLogs and eth_getTransactionReceipt
- Check that the logs from eth_getLogs are also found from eth_getTransactionReceipt
- Check that the logs from eth_getTransactionReceipt are also found from eth_getLogs
- Check that logs from eth_getLogs are not from failed transactions

Note that this might not detect all missing logs from eth_getLogs.

Run like this:

    python3 check_log_inconsistencies.py --rpc http://localhost:4445 --from-block 3581430 --to-block 3581530

Python 3.6 or later required. No external libraries required.
"""
import argparse
from collections import Counter
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import request


def main():
    parser = argparse.ArgumentParser("Check for inconsistencies in logs")
    parser.add_argument('--rpc', type=str, help="rpc url", required=True)
    parser.add_argument('--from-block', type=int, help="from block", required=True)
    parser.add_argument('--to-block', type=int, help="to block", required=True)
    parser.add_argument('--batch-size', type=int, help="number of blocks to get in single request", default=100)
    args = parser.parse_args()

    print(
        f"Checking for inconsistencies in logs returned by eth_getLogs and eth_getTransactionReceipt "
        f"between blocks {args.from_block} and {args.to_block}."
    )
    inconsistencies = []
    client = JSONRPCClient(args.rpc)
    from_block = args.from_block
    to_block = args.to_block
    while from_block <= to_block:
        batch_to_block = min(from_block + args.batch_size, to_block)
        print(f"Checking blocks {from_block} to {batch_to_block} (up to {to_block})")
        logs = client.get_logs(from_block, batch_to_block)
        batch_inconsistencies = check_inconsistencies(
            client=client,
            logs=logs
        )
        if batch_inconsistencies:
            inconsistencies.extend(batch_inconsistencies)
        from_block = batch_to_block + 1

    if inconsistencies:
        print("\n\nDetected inconsistencies:")
        type_counter = Counter()
        for inconsistency in inconsistencies:
            type_counter[inconsistency.type] += 1
            print(inconsistency)
        print(
            f"Total of {len(inconsistencies)} inconsistencies detected between blocks "
            f"{args.from_block} and {args.to_block}."
        )
        print("Inconsistencies by types:")
        for inconsistency_type, count in type_counter.most_common():
            print(inconsistency_type.ljust(45), count)
    else:
        print(f"No inconsistencies detected between blocks {args.from_block} and {args.to_block}.")


class JSONRPCClient:
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    def jsonrpc_request(self, method: str, params: Any) -> Any:
        json_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        req = request.Request(
            self.rpc_url,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
            data=json.dumps(json_data).encode('utf-8')
        )
        with request.urlopen(req) as f:
            data = json.load(f)
        try:
            return data['result']
        except KeyError as e:
            raise Exception(f'Invalid JSONRPC response: {data!r}') from e

    def get_logs(self, from_block: int, to_block: int) -> List[Dict[str, Any]]:
        response = self.jsonrpc_request(
            "eth_getLogs",
            [{"fromBlock": hex(from_block), "toBlock": hex(to_block)}],
        )
        return response

    def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        response = self.jsonrpc_request(
            "eth_getTransactionReceipt",
            [tx_hash],
        )
        return response


@dataclass
class LogInconsistency:
    tx_hash: str
    log_index: int
    block_number: int
    receipt_log: Optional[Dict[str, Any]]
    getlogs_log: Optional[Dict[str, Any]]
    type: str

    def __repr__(self):
        receipt_data = self.receipt_log['data'] if self.receipt_log else '(none)'
        getlogs_data = self.getlogs_log['data'] if self.getlogs_log else '(none)'
        lines = [
            f"<INCONSISTENCY(",
            f"  block: {self.block_number}, tx: {self.tx_hash}, index: {self.log_index}",
            f"  type: {self.type}",
            f"  receipt data: {receipt_data}",
            f"  getlogs data: {getlogs_data}",
            ")>",
        ]
        return '\n'.join(lines)


def check_inconsistencies(client: JSONRPCClient, logs: List[Dict[str, any]]):
    logs_by_tx_hash_and_log_index = {}
    tx_hashes = set()
    for log in logs:
        tx_hashes.add(log['transactionHash'])
        log_key = (log['transactionHash'], log['logIndex'])
        assert log_key not in logs_by_tx_hash_and_log_index, f'{log_key} would be replaced'
        logs_by_tx_hash_and_log_index[log_key] = log

    failed_tx_hashes = set()
    inconsistencies = []
    print(f"{len(tx_hashes)} transactions")
    for i, tx_hash in enumerate(tx_hashes, start=1):
        # print(f"Checking {tx_hash}")
        print_percentage_progress(i, len(tx_hashes))
        tx_receipt = client.get_transaction_receipt(tx_hash)

        if int(tx_receipt['status'], 16) == 0:
            print(f"NOTE: Transaction {tx_hash} is failed, should not have logs")
            failed_tx_hashes.add(tx_hash)
            continue  # process these later

        for receipt_log in tx_receipt['logs']:
            log_key = (tx_hash, receipt_log['logIndex'])
            try:
                getlogs_log = logs_by_tx_hash_and_log_index[log_key]
            except KeyError:
                print(f"INCONSISTENCY DETECTED! Log {log_key} found in tx receipt but not in eth_getLogs response!")
                inconsistencies.append(LogInconsistency(
                    tx_hash=tx_hash,
                    log_index=int(receipt_log['logIndex'], 16),
                    block_number=int(receipt_log['blockNumber'], 16),
                    type='log missing from eth_getLogs',
                    receipt_log=receipt_log,
                    getlogs_log=None
                ))
            else:
                inconsistency = check_data_mismatch(
                    receipt_log=receipt_log,
                    getlogs_log=getlogs_log,
                )
                if inconsistency:
                    print("INCONSISTENCY DETECTED -- data mismatch")
                    print(inconsistency)
                    inconsistencies.append(inconsistency)

                # Delete this so we know the things that are left
                del logs_by_tx_hash_and_log_index[log_key]

    for failed_tx_hash in failed_tx_hashes:
        log_keys = list(k for k in logs_by_tx_hash_and_log_index.keys() if k[0] == failed_tx_hash)
        for log_key in log_keys:
            print(f"INCONSISTENCY! Log {log_key} is from a failed transaction.")
            getlogs_log = logs_by_tx_hash_and_log_index[log_key]
            inconsistencies.append(LogInconsistency(
                tx_hash=failed_tx_hash,
                log_index=int(getlogs_log['logIndex'], 16),
                block_number=int(getlogs_log['blockNumber'], 16),
                type='log from failed tx found in eth_getLogs',
                receipt_log=None,
                getlogs_log=getlogs_log
            ))
            del logs_by_tx_hash_and_log_index[log_key]

    # Nothing leftover should be here
    for log_key, getlogs_log in logs_by_tx_hash_and_log_index.items():
        print(f"INCONSISTENCY! Log {log_key} found from eth_getLogs but not from eth_getTransactionReceipt")
        inconsistencies.append(LogInconsistency(
            tx_hash=getlogs_log['transactionHash'],
            log_index=int(getlogs_log['logIndex'], 16),
            block_number=int(getlogs_log['blockNumber'], 16),
            type='log missing from eth_getTransactionReceipt',
            receipt_log=None,
            getlogs_log=getlogs_log
        ))

    return inconsistencies


def check_data_mismatch(receipt_log: Dict[str, Any], getlogs_log: Dict[str, Any]) -> Optional[LogInconsistency]:
    if receipt_log['data'] != getlogs_log['data']:
        return LogInconsistency(
            tx_hash=receipt_log['transactionHash'],
            log_index=int(receipt_log['logIndex'], 16),
            block_number=int(receipt_log['blockNumber'], 16),
            type='data mismatch',
            receipt_log=receipt_log,
            getlogs_log=getlogs_log,
        )
    return None


def print_percentage_progress(i, length):
    if length >= 10:
        if i % (length // 10) == 0:
            print(i // (length // 10) * 10, '% ...')


if __name__ == '__main__':
    main()
