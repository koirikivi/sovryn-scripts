import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List

from eth_utils import to_hex


logger = logging.getLogger(__name__)


# Loan with more human-readable data
@dataclass
class Loan:
    loan_id: str
    loan_token_address: str
    collateral_token_address: str
    principal_wei: int
    collateral_wei: int
    interest_owed_per_day_wei: int
    interest_deposit_remaining_wei: int
    start_rate: Decimal
    start_margin: Decimal
    maintenance_margin: Decimal
    current_margin: Decimal
    max_loanterm: int
    end_timestamp: int
    max_liquidatable_wei: int
    max_seizable_wei: int

    @classmethod
    def from_raw(cls, raw) -> 'Loan':
        return cls(
            loan_id=to_hex(raw[0]),  # str
            loan_token_address=raw[1],  # str
            collateral_token_address=raw[2],  # str
            principal_wei=raw[3],  # int
            collateral_wei=raw[4],  # int
            interest_owed_per_day_wei=raw[5],  # int
            interest_deposit_remaining_wei=raw[6],  # int
            start_rate=Decimal(raw[7]) / 10 ** 18,  # Decimal
            start_margin=Decimal(raw[8]) / 10 ** 18,  # Decimal
            maintenance_margin=Decimal(raw[9]) / 10 ** 18,  # Decimal
            current_margin=Decimal(raw[10]) / 10 ** 18,  # Decimal
            max_loanterm=raw[11],  # int
            end_timestamp=raw[12],  # int
            max_liquidatable_wei=raw[13],  # int
            max_seizable_wei=raw[14],  # int
        )


def load_active_loans(*, sovryn_protocol, block_identifier='latest') -> List[Loan]:
    start = 0
    count = 250
    raw_loans = []
    while True:
        end = start + count
        logger.info(f"Fetching active loans (batch: {start}-{end - 1})")
        batch = sovryn_protocol.functions.getActiveLoans(
            start,
            count,
            False
        ).call(block_identifier=block_identifier)
        logger.info(f"Got {len(batch)} loans in batch")
        raw_loans.extend(batch)
        if len(batch) < count:
            break
        start += count
    logger.info(f"Got {len(raw_loans)} loans in total")
    return [
        Loan.from_raw(raw)
        for raw in raw_loans
    ]
