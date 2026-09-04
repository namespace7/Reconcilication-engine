from datetime import datetime
from decimal import Decimal

from .domain import CanonicalTransaction, Side, TransactionStatus

SIDE_MAP = {
    "B": Side.BUY,
    "BUY": Side.BUY,
    "S": Side.SELL,
    "SELL": Side.SELL
}

def normalize_record(record: dict) -> CanonicalTransaction:
    side_value = record["side"]
    side = SIDE_MAP[side_value.upper()]

    return CanonicalTransaction(
        source_reference = record["reference"],
        timestamp = datetime.fromisoformat(record["timestamp"]),
        instrument = record["instrument"].upper(),
        side = side,
        quantity = Decimal(str(record["quantity"])),
        unit_price = Decimal(str(record["unit_price"])),
        amount = Decimal(str(record["amount"])),
        status = TransactionStatus(record["status"].upper()),
    )
