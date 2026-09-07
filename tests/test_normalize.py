from datetime import datetime
from decimal import Decimal
from datetime import datetime, timezone

from reconciliation.domain import Side, TransactionStatus
from reconciliation.normalize import normalize_record

def test_normalizes_external_transaction():
    record = {
        "reference" : "T-1001",
        "timestamp": "2026-09-01T10:30:00",
        "instrument": "btc",
        "side": "B",
        "quantity": "0.5",
        "unit_price": "62000",
        "amount": "31000",
        "status": "settled",
    }

    result = normalize_record(record)

    assert result.source_reference == "T-1001"
    assert result.timestamp == datetime(
    2026,
    9,
    1,
    10,
    30,
    tzinfo=timezone.utc,
    )
    assert result.instrument == "BTC"
    assert result.side == Side.BUY
    assert result.quantity == Decimal("0.5")
    assert result.unit_price == Decimal("62000")
    assert result.amount == Decimal("31000")
    assert result.status == TransactionStatus.SETTLED

def test_normalizes_zulu_timestamp_as_utc():
    record = {
        "reference": "T-1001",
        "timestamp": "2025-07-01T09:15:00Z",
        "instrument": "BTC-USD",
        "side": "BUY",
        "quantity": "0.50",
        "unit_price": "62000.00",
        "amount": "31000.00",
        "status": "SETTLED",
    }

    result = normalize_record(record)

    assert result.timestamp == datetime(
        2025,
        7,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )

def test_normalizes_timezone_naive_timestamp_as_utc():
    record = {
        "reference": "T-1001",
        "timestamp": "2025-07-01 09:15:00",
        "instrument": "BTC-USD",
        "side": "B",
        "quantity": "0.50",
        "unit_price": "62000.00",
        "amount": "31000.00",
        "status": "SETTLED",
    }

    result = normalize_record(record)

    assert result.timestamp == datetime(
        2025,
        7,
        1,
        9,
        15,
        tzinfo=timezone.utc,
    )