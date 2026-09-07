from datetime import datetime
from decimal import Decimal

from .domain import CanonicalTransaction, Side, TransactionStatus

SIDE_MAP = {
    "B": Side.BUY,
    "BUY": Side.BUY,
    "S": Side.SELL,
    "SELL": Side.SELL
}

from datetime import datetime, timezone


def parse_timestamp(value: str) -> datetime:
    value = value.strip()

    # Python 3.9's fromisoformat() does not accept "Z".
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    # Source timestamps without an explicit timezone are assumed to be UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def normalize_record(record: dict) -> CanonicalTransaction:
    side_value = record["side"]
    side = SIDE_MAP[side_value.upper()]

    return CanonicalTransaction(
        source_reference = record["reference"],
        timestamp = parse_timestamp(record["timestamp"]),
        instrument = record["instrument"].upper(),
        side = side,
        quantity = Decimal(str(record["quantity"])),
        unit_price = Decimal(str(record["unit_price"])),
        amount = Decimal(str(record["amount"])),
        status = TransactionStatus(record["status"].upper()),
    )


