#FROM ubuntu:20.04
FROM python:3.8-buster

#RUN apt-get update
#RUN apt-get upgrade -y
#
#RUN python3.8 -m pip install --upgrade pip
#RUN python -m venv /srv/venv
COPY ./requirements-minimal.txt /srv/requirements-minimal.txt
RUN pip install -r /srv/requirements-minimal.txt
COPY ./abi /srv/abi
COPY ./constants.py /srv/constants.py
COPY ./utils.py /srv/utils.py
COPY ./vote_bridge_tx.py /srv/vote_bridge_tx.py
COPY ./check_fastbtc_in_tx.py /srv/check_fastbtc_in_tx.py

WORKDIR /srv
ENTRYPOINT ["python"]

