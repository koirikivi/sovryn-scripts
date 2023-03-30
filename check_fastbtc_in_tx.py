import json
import os
from utils import to_address, get_web3, load_abi

# TO get debug output, create fastbtc_in_federators.json that looks like this
# [
#  [ "name1", "0x1234..."],
#  [ "name2", "0xf00ba2..."]
# ]
FEDS = []
FEDERATORS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'fastbtc_in_federators.json')
if os.path.exists(FEDERATORS_JSON_PATH):
    with open(FEDERATORS_JSON_PATH, 'r') as f:
        FEDS = [(r[0], to_address(r[1])) for r in json.load(f)]


MULTISIG_ADDRESS = to_address('0x0f279E810B95E0D425622b9B40D7Bcd0B5C4b19D')


def show_confirmation_details(tx_number):
    web3 = get_web3('rsk_mainnet')
    multisig = web3.eth.contract(
        address=MULTISIG_ADDRESS,
        abi=load_abi('fastbtc/Multisig'),
    )
    bridge_multisig_rows = FEDS
    required = multisig.functions.required().call()
    confirmations = 0
    confirmation_left_from = []
    for owner in multisig.functions.getOwners().call():
        has_confirmed = multisig.functions.confirmations(tx_number, owner).call()
        if has_confirmed:
            confirmations += 1
        else:
            try:
                owner_row = [r for r in bridge_multisig_rows if r[1] == owner][0]
                confirmation_left_from.append(owner_row)
            except IndexError:
                pass
    print(f'Multisig address: `{multisig.address}`')
    print(f'Transaction id: `{tx_number}`')
    is_confirmed = multisig.functions.isConfirmed(tx_number).call()
    print('Is confirmed?: ', is_confirmed)
    if is_confirmed:
        print('Transaction is confirmed, no need to confirm it again')
        return
    print('SSH to your fastbtc-in node, `cd` to the `fastBTC-confirmation-node/scripts` and run')
    print(f'```\nnodejs -r esm confirmTx mainnet {tx_number}\n# OR, if nodejs is not found:\nnode -r esm confirmTx mainnet {tx_number}\n```')
    hex_data = multisig.encodeABI('confirmTransaction', [tx_number])
    print(
        f'Or to confirm using metamask, enable hex data in the advanced settings, and then send a transaction without any value\nto `{multisig.address}`\n'
        f'and add this to the `hex data` field:\n`{hex_data}`'
    )
    print(f"{confirmations} out of {required} confirmations received, {required - confirmations} left")
    if confirmation_left_from:
        print("")
        print("Relevant MultiSig addresses for signers:")
        for discord_nick, address in confirmation_left_from:
            print(f"{discord_nick} `{address}`")
    print("============================================================")
    print("")


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description='Show confirmation details for a given transaction number in the FastBTC-in multisig')
    parser.add_argument('tx_number', type=int)
    args = parser.parse_args()
    show_confirmation_details(args.tx_number)


if __name__ == '__main__':
    main()

