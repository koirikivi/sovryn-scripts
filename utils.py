"""Various web3"""
from datetime import datetime, timezone
import functools
import json
import logging
import os
import sys
from time import sleep
from typing import Dict, Any, Union

from eth_typing import AnyAddress
from eth_utils import to_checksum_address, to_hex
from web3 import Web3
from web3.contract import Contract, ContractEvent

THIS_DIR = os.path.dirname(__file__)
ABI_DIR = os.path.join(THIS_DIR, 'abi')
logger = logging.getLogger(__name__)

RPC_URLS = {
    'rsk_mainnet': 'https://mainnet2.sovryn.app/rpc',
    'bsc_mainnet': 'https://bsc-dataseed.binance.org/',
    'rsk_testnet': 'https://testnet2.sovryn.app/rpc',
    'bsc_testnet': 'https://data-seed-prebsc-1-s1.binance.org:8545/',
    'eth_mainnet': 'https://mainnet.infura.io/v3/YOUR_API_KEY',  # From Bridge-SC
    'eth_testnet_ropsten': 'https://ropsten.infura.io/v3/YOUR_API_KEY',  # From Bridge-SC
}


def get_web3(chain_name: str):
    try:
        rpc_url = RPC_URLS[chain_name]
    except KeyError:
        valid_chains = ', '.join(repr(k) for k in RPC_URLS.keys())
        raise LookupError(f'Invalid chain name: {chain_name!r}. Valid options: {valid_chains}')
    return Web3(Web3.HTTPProvider(rpc_url))


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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_abi(name: str) -> Dict[str, Any]:
    abi_path = os.path.join(ABI_DIR, f'{name}.json')
    assert os.path.abspath(abi_path).startswith(os.path.abspath(ABI_DIR))
    with open(abi_path) as f:
        return json.load(f)


def to_address(a: Union[bytes, str]) -> AnyAddress:
    # Web3.py expects checksummed addresses, but has no support for EIP-1191,
    # so RSK-checksummed addresses are broken
    # Should instead fix web3, but meanwhile this wrapper will help us
    return to_checksum_address(a)


ERC20_ABI = load_abi('IERC20')


@functools.lru_cache()
def get_erc20_contract(*, token_address: Union[str, AnyAddress], web3: Web3) -> Contract:
    return web3.eth.contract(
        address=to_address(token_address),
        abi=ERC20_ABI,
    )


def get_events(
        *,
        event: ContractEvent,
        from_block: int,
        to_block: int,
        batch_size: int = 100
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
        event_filter = event.createFilter(
            fromBlock=batch_from_block,
            toBlock=batch_to_block,
        )
        events = event_filter.get_all_entries()
        if len(events) > 0:
            logger.info(f'found %s events in batch', len(events))
        ret.extend(events)
        batch_from_block = batch_to_block + 1
    logger.info(f'found %s events in total', len(ret))
    return ret


def exponential_sleep(attempt, max_sleep_time=256.0):
    sleep_time = min(2 ** attempt, max_sleep_time)
    sleep(sleep_time)


def retryable(*, max_attempts: int = 10):
    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt >= max_attempts:
                        logger.warning('max attempts (%s) exchusted for error: %s', max_attempts, e)
                        raise
                    logger.warning(
                        'Retryable error (attempt: %s/%s): %s',
                        attempt + 1,
                        max_attempts,
                        e,
                        )
                    exponential_sleep(attempt)
                    attempt += 1
        return wrapped
    return decorator


class UserDataNotAddress(Exception):
    def __init__(self, userdata: bytes):
        super().__init__(f'userdata {userdata!r} cannot be decoded to an address')


@functools.lru_cache()
def is_contract(*, web3: Web3, address: str) -> bool:
    code = web3.eth.get_code(to_address(address))
    return code != b'\x00'
