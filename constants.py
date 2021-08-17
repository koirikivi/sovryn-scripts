from utils import load_abi


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
    'rsk_bsc_mainnet': {
        'rsk': {
            'bridge_address': '0x971b97c8cc82e7d27bc467c2dc3f219c6ee2e350',
            'federation_address': '0xc4b5178cc086e764568adfb2daccbb0d973e8132',
            'bridge_start_block': 3399221,
            'chain': 'rsk_mainnet',
        },
        'other': {
            'bridge_address': '0xdfc7127593c8af1a17146893f10e08528f4c2aa7',
            'federation_address': '0xfc321356bb2ca3d68fafe9515c24c9b23b63a6a6',
            'bridge_start_block': 7917126,
            'chain': 'bsc_mainnet',
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
    },
    'rsk_bsc_testnet': {
        'rsk': {
            'bridge_address': '0x2b2bcad081fa773dc655361d1bb30577caa556f8',
            'federation_address': '0x92f791b72842f479888aefba975eff2ed74700b7',
            'bridge_start_block': 1884421,
            'chain': 'rsk_testnet',
        },
        'other': {
            'bridge_address': '0x862e8aff917319594cc7faaae5350d21196c086f',
            'federation_address': '0x2b456e230225c4670fbf10b9da506c019a24cac7',
            'bridge_start_block': 9290364,
            'chain': 'bsc_testnet',
        }
    },
}
BRIDGE_ABI = load_abi('token_bridge/Bridge')
FEDERATION_ABI = load_abi('token_bridge/Federation')