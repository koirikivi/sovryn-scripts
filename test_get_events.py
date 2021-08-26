from utils import get_web3, get_events, enable_logging, to_address
from constants import BRIDGE_ABI, BRIDGES


def main():
    enable_logging()
    web3 = get_web3('rsk_mainnet')
    bridge_address = BRIDGES['rsk_eth_mainnet']['rsk']['bridge_address']
    bridge_contract = web3.eth.contract(
        address=to_address(bridge_address),
        abi=BRIDGE_ABI
    )
    events = get_events(
        event=bridge_contract.events.Cross,
        from_block=3633069,
        to_block=3633569,
        batch_size=500,
    )
    print(events)


if __name__ == '__main__':
    main()