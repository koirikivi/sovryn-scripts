from collections import defaultdict
from decimal import Decimal
from pprint import pprint
from dataclasses import asdict
from utils import get_web3, load_abi, enable_logging, get_erc20_contract
from constants import SOVRYN_PROTOCOL_ADDRESS
from loans import load_active_loans


def main():
    web3 = get_web3('rsk_mainnet')
    sovryn_protocol = web3.eth.contract(
        address=SOVRYN_PROTOCOL_ADDRESS,
        abi=load_abi('loans/SovrynProtocol')
    )

    loans = load_active_loans(
        sovryn_protocol=sovryn_protocol
    )

    num_liquidatable = 0
    token_addresses = set()
    max_liquidatable = defaultdict(int)
    max_seizable = defaultdict(int)
    for loan in loans:
        if loan.max_seizable_wei:
            num_liquidatable += 1
        max_liquidatable[loan.loan_token_address] += loan.max_liquidatable_wei
        max_seizable[loan.collateral_token_address] += loan.max_seizable_wei
        token_addresses |= {loan.loan_token_address, loan.collateral_token_address}

    for token_address in token_addresses:
        token = get_erc20_contract(
            token_address=token_address,
            web3=web3,
        )
        print(f'{token.functions.name().call()} ({token.functions.symbol().call()})')
        decimals = token.functions.decimals().call()
        max_liquidatable_decimal = Decimal(max_liquidatable[token_address]) / 10**decimals
        max_seizable_decimal = Decimal(max_seizable[token_address]) / 10**decimals
        print(f'Max liquidatable: {max_liquidatable_decimal:20.6f}')
        print(f'Max seizable:     {max_seizable_decimal:20.6f}')
        print('')
    print("Total", num_liquidatable, "loans liquidatable (out of", len(loans), "loans in total)")


if __name__ == '__main__':
    enable_logging()
    main()
