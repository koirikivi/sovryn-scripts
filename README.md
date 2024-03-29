misc. scripts for sovryn
========================

Various scripts for Sovryn, stored in this repo for reuse.

Most (all?) are implemented in Python since this is first and foremost
Rainer's playground and I feel most at home when charming snakes.

Usage
-----

```shell
python3.8 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt

python some_script_file.py
```

Some documented scripts
-----------------------

Show status and confirmation details of a FastBTC-in transaction:

```shell
venv/bin/python check_fastbtc_in_tx.py <tx_number>
```

Vote a stuck token bridge TX:

```shell
venv/bin/python vote_bridge_tx.py --bridge rsk_bsc_mainnet --deposit-chain rsk --tx-hash 0x123..
````


Use (docker)
------------

```shell
docker build -t sovryn_scripts .
docker run -it sovryn_scripts -- vote_bridge_tx.py --bridge rsk_bsc_mainnet --deposit-chain rsk --tx-hash 0x123..
```

(only some scripts copied to docker so far, copy the others in `Dockerfile` as needed)
