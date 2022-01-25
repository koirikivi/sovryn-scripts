import logging
import dataclasses
import enum
import json
import logging
import sys
from collections import defaultdict
from time import sleep
from typing import Optional

from eth_utils import to_hex
from web3 import Web3
from web3.contract import Contract, ContractEvent

logger = logging.getLogger(__name__)


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
    status: TransferStatus
    bitcoin_tx_id: Optional[str] = None


def main():
    enable_logging()

    rsk_web3 = Web3(Web3.HTTPProvider('https://testnet.sovryn.app/rpc'))
    fastbtc_bridge = get_fastbtc_contract(
        web3=rsk_web3,
        address='0x53b202E87Eb5F60a9779c4Dcae14c1037D2C0422'
    )

    from_block = 2326996
    to_block = rsk_web3.eth.get_block_number()
    user_address = ''
    try:
        user_address = sys.argv[2]
        print("Showing transfers from user", user_address)
    except IndexError:
        print("Showing transfers from all users")


    # TODO: this can be optimized at least by reducing the amount of calls needed,
    # and by utilizing filters better
    new_bitcoin_transfer_events = get_events(
        event=fastbtc_bridge.events.NewBitcoinTransfer(),
        from_block=from_block,
        to_block=to_block,
        argument_filters=dict(
           rskAddress=user_address,
        ) if user_address else None
    )
    print("Found", len(new_bitcoin_transfer_events), "NewBitcoinTransfer events")


    bitcoin_transfer_batch_sending_events = get_events(
        event=fastbtc_bridge.events.BitcoinTransferBatchSending(),
        from_block=from_block,
        to_block=to_block,
    )
    print("Found", len(bitcoin_transfer_batch_sending_events), "BitcoinTransferBatchSending events")

    bitcoin_transfer_status_updated_events = get_events(
        event=fastbtc_bridge.events.BitcoinTransferStatusUpdated(),
        from_block=from_block,
        to_block=to_block,
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
            status=statuses_by_transfer_id.get(event.args.transferId, TransferStatus.NEW),
            bitcoin_tx_id=bitcoin_tx_id,
        )
        transfers.append(transfer)

    for transfer in transfers:
        print(transfer)


def get_fastbtc_contract(web3, address) -> Contract:
    fastbtc_abi = json.loads("""[
        {
            "inputs": [
                {
                    "internalType": "address",
                    "name": "accessControl",
                    "type": "address"
                },
                {
                    "internalType": "contract IBTCAddressValidator",
                    "name": "newBtcAddressValidator",
                    "type": "address"
                }
            ],
            "stateMutability": "nonpayable",
            "type": "constructor"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "bytes32",
                    "name": "bitcoinTxHash",
                    "type": "bytes32"
                },
                {
                    "indexed": false,
                    "internalType": "uint8",
                    "name": "transferBatchSize",
                    "type": "uint8"
                }
            ],
            "name": "BitcoinTransferBatchSending",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "baseFeeSatoshi",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "dynamicFee",
                    "type": "uint256"
                }
            ],
            "name": "BitcoinTransferFeeChanged",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "bytes32",
                    "name": "transferId",
                    "type": "bytes32"
                },
                {
                    "indexed": false,
                    "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                    "name": "newStatus",
                    "type": "uint8"
                }
            ],
            "name": "BitcoinTransferStatusUpdated",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "address",
                    "name": "account",
                    "type": "address"
                }
            ],
            "name": "Frozen",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": true,
                    "internalType": "bytes32",
                    "name": "transferId",
                    "type": "bytes32"
                },
                {
                    "indexed": false,
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "nonce",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "amountSatoshi",
                    "type": "uint256"
                },
                {
                    "indexed": false,
                    "internalType": "uint256",
                    "name": "feeSatoshi",
                    "type": "uint256"
                },
                {
                    "indexed": true,
                    "internalType": "address",
                    "name": "rskAddress",
                    "type": "address"
                }
            ],
            "name": "NewBitcoinTransfer",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "address",
                    "name": "account",
                    "type": "address"
                }
            ],
            "name": "Paused",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "address",
                    "name": "account",
                    "type": "address"
                }
            ],
            "name": "Unfrozen",
            "type": "event"
        },
        {
            "anonymous": false,
            "inputs": [
                {
                    "indexed": false,
                    "internalType": "address",
                    "name": "account",
                    "type": "address"
                }
            ],
            "name": "Unpaused",
            "type": "event"
        },
        {
            "inputs": [],
            "name": "DYNAMIC_FEE_DIVISOR",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "MAXIMUM_VALID_NONCE",
            "outputs": [
                {
                    "internalType": "uint8",
                    "name": "",
                    "type": "uint8"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "MAX_BASE_FEE_SATOSHI",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "SATOSHI_DIVISOR",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "accessControl",
            "outputs": [
                {
                    "internalType": "contract IFastBTCAccessControl",
                    "name": "",
                    "type": "address"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "feeStructureIndex",
                    "type": "uint256"
                },
                {
                    "internalType": "uint256",
                    "name": "newBaseFeeSatoshi",
                    "type": "uint256"
                },
                {
                    "internalType": "uint256",
                    "name": "newDynamicFee",
                    "type": "uint256"
                }
            ],
            "name": "addFeeStructure",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "baseFeeSatoshi",
            "outputs": [
                {
                    "internalType": "uint32",
                    "name": "",
                    "type": "uint32"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "btcAddressValidator",
            "outputs": [
                {
                    "internalType": "contract IBTCAddressValidator",
                    "name": "",
                    "type": "address"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "amountSatoshi",
                    "type": "uint256"
                }
            ],
            "name": "calculateCurrentFeeSatoshi",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "amountWei",
                    "type": "uint256"
                }
            ],
            "name": "calculateCurrentFeeWei",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "currentFeeStructureIndex",
            "outputs": [
                {
                    "internalType": "uint8",
                    "name": "",
                    "type": "uint8"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "dynamicFee",
            "outputs": [
                {
                    "internalType": "uint16",
                    "name": "",
                    "type": "uint16"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "federators",
            "outputs": [
                {
                    "internalType": "address[]",
                    "name": "addresses",
                    "type": "address[]"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "",
                    "type": "uint256"
                }
            ],
            "name": "feeStructures",
            "outputs": [
                {
                    "internalType": "uint32",
                    "name": "baseFeeSatoshi",
                    "type": "uint32"
                },
                {
                    "internalType": "uint16",
                    "name": "dynamicFee",
                    "type": "uint16"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "freeze",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "frozen",
            "outputs": [
                {
                    "internalType": "bool",
                    "name": "",
                    "type": "bool"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                }
            ],
            "name": "getNextNonce",
            "outputs": [
                {
                    "internalType": "uint8",
                    "name": "",
                    "type": "uint8"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                },
                {
                    "internalType": "uint8",
                    "name": "nonce",
                    "type": "uint8"
                }
            ],
            "name": "getTransfer",
            "outputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "rskAddress",
                            "type": "address"
                        },
                        {
                            "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                            "name": "status",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "nonce",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "feeStructureIndex",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint32",
                            "name": "blockNumber",
                            "type": "uint32"
                        },
                        {
                            "internalType": "uint40",
                            "name": "totalAmountSatoshi",
                            "type": "uint40"
                        },
                        {
                            "internalType": "string",
                            "name": "btcAddress",
                            "type": "string"
                        }
                    ],
                    "internalType": "struct FastBTCBridge.BitcoinTransfer",
                    "name": "transfer",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                },
                {
                    "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                    "name": "newStatus",
                    "type": "uint8"
                }
            ],
            "name": "getTransferBatchUpdateHash",
            "outputs": [
                {
                    "internalType": "bytes32",
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "stateMutability": "pure",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32",
                    "name": "bitcoinTxHash",
                    "type": "bytes32"
                },
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                },
                {
                    "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                    "name": "newStatus",
                    "type": "uint8"
                }
            ],
            "name": "getTransferBatchUpdateHashWithTxHash",
            "outputs": [
                {
                    "internalType": "bytes32",
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "stateMutability": "pure",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32",
                    "name": "transferId",
                    "type": "bytes32"
                }
            ],
            "name": "getTransferByTransferId",
            "outputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "rskAddress",
                            "type": "address"
                        },
                        {
                            "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                            "name": "status",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "nonce",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "feeStructureIndex",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint32",
                            "name": "blockNumber",
                            "type": "uint32"
                        },
                        {
                            "internalType": "uint40",
                            "name": "totalAmountSatoshi",
                            "type": "uint40"
                        },
                        {
                            "internalType": "string",
                            "name": "btcAddress",
                            "type": "string"
                        }
                    ],
                    "internalType": "struct FastBTCBridge.BitcoinTransfer",
                    "name": "transfer",
                    "type": "tuple"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                },
                {
                    "internalType": "uint256",
                    "name": "nonce",
                    "type": "uint256"
                }
            ],
            "name": "getTransferId",
            "outputs": [
                {
                    "internalType": "bytes32",
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "stateMutability": "pure",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string[]",
                    "name": "btcAddresses",
                    "type": "string[]"
                },
                {
                    "internalType": "uint8[]",
                    "name": "nonces",
                    "type": "uint8[]"
                }
            ],
            "name": "getTransfers",
            "outputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "rskAddress",
                            "type": "address"
                        },
                        {
                            "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                            "name": "status",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "nonce",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "feeStructureIndex",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint32",
                            "name": "blockNumber",
                            "type": "uint32"
                        },
                        {
                            "internalType": "uint40",
                            "name": "totalAmountSatoshi",
                            "type": "uint40"
                        },
                        {
                            "internalType": "string",
                            "name": "btcAddress",
                            "type": "string"
                        }
                    ],
                    "internalType": "struct FastBTCBridge.BitcoinTransfer[]",
                    "name": "ret",
                    "type": "tuple[]"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                }
            ],
            "name": "getTransfersByTransferId",
            "outputs": [
                {
                    "components": [
                        {
                            "internalType": "address",
                            "name": "rskAddress",
                            "type": "address"
                        },
                        {
                            "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                            "name": "status",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "nonce",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint8",
                            "name": "feeStructureIndex",
                            "type": "uint8"
                        },
                        {
                            "internalType": "uint32",
                            "name": "blockNumber",
                            "type": "uint32"
                        },
                        {
                            "internalType": "uint40",
                            "name": "totalAmountSatoshi",
                            "type": "uint40"
                        },
                        {
                            "internalType": "string",
                            "name": "btcAddress",
                            "type": "string"
                        }
                    ],
                    "internalType": "struct FastBTCBridge.BitcoinTransfer[]",
                    "name": "ret",
                    "type": "tuple[]"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                }
            ],
            "name": "isValidBtcAddress",
            "outputs": [
                {
                    "internalType": "bool",
                    "name": "",
                    "type": "bool"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                },
                {
                    "internalType": "bytes[]",
                    "name": "signatures",
                    "type": "bytes[]"
                }
            ],
            "name": "markTransfersAsMined",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32",
                    "name": "bitcoinTxHash",
                    "type": "bytes32"
                },
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                },
                {
                    "internalType": "bytes[]",
                    "name": "signatures",
                    "type": "bytes[]"
                }
            ],
            "name": "markTransfersAsSending",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "maxTransferSatoshi",
            "outputs": [
                {
                    "internalType": "uint40",
                    "name": "",
                    "type": "uint40"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "minTransferSatoshi",
            "outputs": [
                {
                    "internalType": "uint40",
                    "name": "",
                    "type": "uint40"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "",
                    "type": "string"
                }
            ],
            "name": "nextNonces",
            "outputs": [
                {
                    "internalType": "uint8",
                    "name": "",
                    "type": "uint8"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "pause",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "paused",
            "outputs": [
                {
                    "internalType": "bool",
                    "name": "",
                    "type": "bool"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32[]",
                    "name": "transferIds",
                    "type": "bytes32[]"
                },
                {
                    "internalType": "bytes[]",
                    "name": "signatures",
                    "type": "bytes[]"
                }
            ],
            "name": "refundTransfers",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "contract IBTCAddressValidator",
                    "name": "newBtcAddressValidator",
                    "type": "address"
                }
            ],
            "name": "setBtcAddressValidator",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "feeStructureIndex",
                    "type": "uint256"
                }
            ],
            "name": "setCurrentFeeStructure",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "newMaxTransferSatoshi",
                    "type": "uint256"
                }
            ],
            "name": "setMaxTransferSatoshi",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "newMinTransferSatoshi",
                    "type": "uint256"
                }
            ],
            "name": "setMinTransferSatoshi",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                }
            ],
            "name": "transferToBtc",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "bytes32",
                    "name": "",
                    "type": "bytes32"
                }
            ],
            "name": "transfers",
            "outputs": [
                {
                    "internalType": "address",
                    "name": "rskAddress",
                    "type": "address"
                },
                {
                    "internalType": "enum FastBTCBridge.BitcoinTransferStatus",
                    "name": "status",
                    "type": "uint8"
                },
                {
                    "internalType": "uint8",
                    "name": "nonce",
                    "type": "uint8"
                },
                {
                    "internalType": "uint8",
                    "name": "feeStructureIndex",
                    "type": "uint8"
                },
                {
                    "internalType": "uint32",
                    "name": "blockNumber",
                    "type": "uint32"
                },
                {
                    "internalType": "uint40",
                    "name": "totalAmountSatoshi",
                    "type": "uint40"
                },
                {
                    "internalType": "string",
                    "name": "btcAddress",
                    "type": "string"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "unfreeze",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "unpause",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256"
                },
                {
                    "internalType": "address payable",
                    "name": "receiver",
                    "type": "address"
                }
            ],
            "name": "withdrawRbtc",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {
                    "internalType": "contract IERC20",
                    "name": "token",
                    "type": "address"
                },
                {
                    "internalType": "uint256",
                    "name": "amount",
                    "type": "uint256"
                },
                {
                    "internalType": "address",
                    "name": "receiver",
                    "type": "address"
                }
            ],
            "name": "withdrawTokens",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]""")
    return web3.eth.contract(abi=fastbtc_abi, address=address)


def get_events(
    *,
    event: ContractEvent,
    from_block: int,
    to_block: int,
    batch_size: int = 50_000,
    argument_filters=None
):
    """Load events in batches"""
    if to_block < from_block:
        raise ValueError(f'to_block {to_block} is smaller than from_block {from_block}')

    logger.info('fetching events from %s to %s with batch size %s', from_block, to_block, batch_size)
    ret = []
    batch_from_block = from_block
    while batch_from_block <= to_block:
        batch_to_block = min(batch_from_block + batch_size, to_block)
        logger.info('fetching batch from %s to %s (up to %s)', batch_from_block, batch_to_block, to_block)

        events = get_event_batch_with_retries(
            event=event,
            from_block=batch_from_block,
            to_block=batch_to_block,
            argument_filters=argument_filters,
        )
        if len(events) > 0:
            logger.info(f'found %s events in batch', len(events))
        ret.extend(events)
        batch_from_block = batch_to_block + 1
    logger.info(f'found %s events in total', len(ret))
    return ret


def get_event_batch_with_retries(event, from_block, to_block, *, argument_filters=None, retries=10):
    while True:
        try:
            return event.getLogs(
                fromBlock=from_block,
                toBlock=to_block,
                argument_filters=argument_filters
            )
        except Exception as e:
            if retries <= 0:
                raise e
            logger.warning('error in get_all_entries: %s, retrying (%s)', e, retries)
            retries -= 1


def exponential_sleep(attempt, max_sleep_time=256.0):
    sleep_time = min(2 ** attempt, max_sleep_time)
    sleep(sleep_time)


def enable_logging():
    root = logging.getLogger()
    root.setLevel(logging.NOTSET)
    formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] %(message)s')

    error_handler = logging.StreamHandler(sys.stderr)
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    info_handler = logging.StreamHandler(sys.stdout)
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root.addHandler(info_handler)


if __name__ == '__main__':
    main()
