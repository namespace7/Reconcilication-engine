from datetime import datetime
from decimal import Decimal

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
    assert result.timestamp == datetime.fromisoformat("2026-09-01T10:30:00")
    assert result.instrument == "BTC"
    assert result.side == Side.BUY
    assert result.quantity == Decimal("0.5")
    assert result.unit_price == Decimal("62000")
    assert result.amount == Decimal("31000")
    assert result.status == TransactionStatus.SETTLED