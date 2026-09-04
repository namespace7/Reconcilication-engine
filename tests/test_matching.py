from datetime import datetime
from decimal import Decimal

from reconciliation.domain import CanonicalTransaction, Side, TransactionStatus
from reconciliation.matching import find_candidates
from reconciliation.rules import ReconciliationRules


def make_transaction(
    reference: str,
    timestamp: str,
    instrument: str = "BTC",
    side: Side = Side.BUY,
    quantity: str = "0.50",
    price: str = "62000",
    amount: str = "31000",
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source_reference=reference,
        timestamp=datetime.fromisoformat(timestamp),
        instrument=instrument,
        side=side,
        quantity=Decimal(quantity),
        unit_price=Decimal(price),
        amount=Decimal(amount),
        status=TransactionStatus.SETTLED,
    )


def default_rules() -> ReconciliationRules:
    return ReconciliationRules(
        time_tolerance_seconds=60,
        quantity_tolerance=Decimal("0"),
        price_tolerance=Decimal("5"),
        amount_tolerance=Decimal("10"),
    )


def test_finds_candidate_when_identity_fields_match():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:37",
    )

    candidates = find_candidates(
        ours,
        [external],
        default_rules(),
    )

    assert len(candidates) == 1
    assert candidates[0].transaction.source_reference == "X-2001"


def test_rejects_candidate_when_side_is_different():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
        side=Side.BUY,
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:10",
        side=Side.SELL,
    )

    candidates = find_candidates(
        ours,
        [external],
        default_rules(),
    )

    assert candidates == []


def test_rejects_candidate_when_quantity_is_outside_tolerance():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
        quantity="0.50",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:10",
        quantity="0.55",
    )

    candidates = find_candidates(
        ours,
        [external],
        default_rules(),
    )

    assert candidates == []


def test_rejects_candidate_when_timestamp_is_outside_tolerance():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:02:00",
    )

    candidates = find_candidates(
        ours,
        [external],
        default_rules(),
    )

    assert candidates == []


def test_closer_candidate_is_ranked_first():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
    )

    farther = make_transaction(
        "X-FAR",
        "2026-09-01T10:00:56",
    )

    closer = make_transaction(
        "X-CLOSE",
        "2026-09-01T10:00:10",
    )

    candidates = find_candidates(
        ours,
        [farther, closer],
        default_rules(),
    )

    assert len(candidates) == 2
    assert candidates[0].transaction.source_reference == "X-CLOSE"
    assert candidates[1].transaction.source_reference == "X-FAR"



def test_exact_reference_is_ranked_as_strong_signal():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
    )

    same_reference = make_transaction(
        "T-1001",
        "2026-09-01T10:00:50",
    )

    different_reference = make_transaction(
        "X-2001",
        "2026-09-01T10:00:10",
    )

    candidates = find_candidates(
        ours,
        [same_reference, different_reference],
        default_rules(),
    )

    assert len(candidates) == 2
    assert candidates[0].transaction.source_reference == "T-1001"
    assert candidates[1].transaction.source_reference == "X-2001"
    assert "source reference matches" in candidates[0].reasons

