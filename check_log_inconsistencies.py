#!/usr/bin/env python3
"""
Check for inconsistencies in log data returned by eth_getLogs and eth_getTransactionReceipt
Note that this won't detect logs that are not returned by eth_getLogs.

Run like this:

    python3 check_log_inconsistencies.py --rpc http://localhost:4445 --from-block 3581430 --to-block 3581530

Python 3.6 or later required. No external libraries required.
"""
import argparse
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
        print(f"Checking blocks {from_block} to {batch_to_block}")
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
        for inconsistency in inconsistencies:
            print(inconsistency)
        print(
            f"Total of {len(inconsistencies)} inconsistencies detected between blocks "
            f"{args.from_block} and {args.to_block}."
        )
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
        return data['result']

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


def check_inconsistencies(client: JSONRPCClient, logs: List[Dict[str, any]]):
    logs_by_tx_hash_and_log_index = {}
    tx_hashes = set()
    for log in logs:
        tx_hashes.add(log['transactionHash'])
        logs_by_tx_hash_and_log_index[(log['transactionHash'], log['logIndex'])] = log

    inconsistencies = []
    print(f"{len(tx_hashes)} transactions")
    for tx_hash in tx_hashes:
        print(f"Checking {tx_hash}")
        tx_receipt = client.get_transaction_receipt(tx_hash)
        for receipt_log in tx_receipt['logs']:
            log_key = (tx_hash, receipt_log['logIndex'])
            try:
                getlogs_log = logs_by_tx_hash_and_log_index[log_key]
            except KeyError:
                print(f"ERROR! Log {log_key} not found in eth_getLogs response!")
                print("Receipt log:")
                print(receipt_log)
                continue
            inconsistency = check_inconsistency(
                receipt_log=receipt_log,
                getlogs_log=getlogs_log,
            )
            if inconsistency:
                print("INCONSISTENCY DETECTED!")
                print(inconsistency)
                inconsistencies.append(inconsistency)
    return inconsistencies


@dataclass
class LogInconsistency:
    tx_hash: str
    log_index: int
    block_number: int
    receipt_log: Dict[str, Any]
    getlogs_log: Dict[str, Any]

    def __repr__(self):
        receipt_data = self.receipt_log['data']
        getlogs_data = self.getlogs_log['data']
        lines = [
            f"<INCONSISTENCY(",
            f"  block: {self.block_number}, tx: {self.tx_hash}, index: {self.log_index}",
            f"  receipt data: {receipt_data}",
            f"  getlogs data: {getlogs_data}",
            ")>",
        ]
        return '\n'.join(lines)


def check_inconsistency(receipt_log: Dict[str, Any], getlogs_log: Dict[str, Any]) -> Optional[LogInconsistency]:
    if receipt_log['data'] != getlogs_log['data']:
        return LogInconsistency(
            tx_hash=receipt_log['transactionHash'],
            log_index=int(receipt_log['logIndex'], 16),
            block_number=int(receipt_log['blockNumber'], 16),
            receipt_log=receipt_log,
            getlogs_log=getlogs_log,
        )
    return None


if __name__ == '__main__':
    main()
