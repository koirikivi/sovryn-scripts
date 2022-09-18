from utils import load_abi, to_address


SOVRYN_PROTOCOL_ADDRESS = to_address('0x5a0d867e0d70fcc6ade25c3f1b89d618b5b4eaa7')
BRIDGES = {
    'rsk_eth_mainnet': {
        'rsk': {
            'bridge_address': '0x1ccad820b6d031b41c54f1f3da11c0d48b399581',
            'federation_address': '0x32593e4f7a4991c2fe17459dae9920fd612855b4',
            #'bridge_start_block': 3373266,
            'bridge_start_block': 3600000,
            'chain': 'rsk_mainnet',
        },
        'other': {
            'bridge_address': '0x33c0d33a0d4312562ad622f91d12b0ac47366ee1',
            'federation_address': '0xD77b76A65a19715BDcB5eE223928af2919836A3E',
            #'bridge_start_block': 12485023,
            'bridge_start_block': 13100000,
            'chain': 'eth_mainnet',
        }
    },
    'rsk_bsc_mainnet': {
        'rsk': {
            'bridge_address': '0x971b97c8cc82e7d27bc467c2dc3f219c6ee2e350',
            'federation_address': '0xD1E45F51C8f09B139218FC75D26409096316971C',
            #'bridge_start_block': 3399221,
            'bridge_start_block': 3600000,
            'chain': 'rsk_mainnet',
        },
        'other': {
            'bridge_address': '0xdfc7127593c8af1a17146893f10e08528f4c2aa7',
            'federation_address': '0x502fBCe27973d4bE1E69a4099046762251D005B4',
            #'bridge_start_block': 7917126,
            'bridge_start_block': 10300000,
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