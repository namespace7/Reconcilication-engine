from datetime import datetime
from decimal import Decimal

from reconciliation.domain import (
    CanonicalTransaction,
    Side,
    TransactionStatus,
)
from reconciliation.engine import (
    ReconciliationStatus,
    reconcile,
)
from reconciliation.rules import ReconciliationRules


def make_transaction(
    reference: str,
    timestamp: str,
    instrument: str = "BTC",
    side: Side = Side.BUY,
    quantity: str = "0.50",
    price: str = "62000",
    amount: str = "31000",
    status: TransactionStatus = TransactionStatus.SETTLED,
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source_reference=reference,
        timestamp=datetime.fromisoformat(timestamp),
        instrument=instrument,
        side=side,
        quantity=Decimal(quantity),
        unit_price=Decimal(price),
        amount=Decimal(amount),
        status=status,
    )


def default_rules() -> ReconciliationRules:
    return ReconciliationRules(
        time_tolerance_seconds=60,
        quantity_tolerance=Decimal("0"),
        price_tolerance=Decimal("5"),
        amount_tolerance=Decimal("10"),
    )


def test_identical_transactions_are_matched():
    ours = [
        make_transaction(
            "T-1001",
            "2026-09-01T10:00:00",
        )
    ]

    external = [
        make_transaction(
            "T-1001",
            "2026-09-01T10:00:00",
        )
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.MATCHED
    assert results[0].match_method == "exact_reference"


def test_transaction_with_acceptable_differences_is_matched():
    ours = [
        make_transaction(
            "T-1001",
            "2026-09-01T10:00:00",
            price="62000",
            amount="31000",
        )
    ]

    external = [
        make_transaction(
            "X-2001",
            "2026-09-01T10:00:30",
            price="62003",
            amount="31005",
        )
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert len(results) == 1
    assert (
        results[0].status
        == ReconciliationStatus.MATCHED_WITH_DIFFERENCES
    )


def test_large_difference_requires_review():
    ours = [
        make_transaction(
            "T-1011",
            "2026-09-01T10:00:00",
            instrument="ETH",
            quantity="10",
            price="3400",
            amount="34000",
        )
    ]

    external = [
        make_transaction(
            "X-2001",
            "2026-09-01T10:00:30",
            instrument="ETH",
            quantity="10",
            price="3417",
            amount="34170",
        )
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert len(results) == 1
    assert results[0].status == ReconciliationStatus.NEEDS_REVIEW
    assert results[0].comparison is not None
    assert results[0].comparison.has_discrepancies is True


def test_unmatched_our_transaction_is_reported():
    ours = [
        make_transaction(
            "T-1001",
            "2026-09-01T10:00:00",
        )
    ]

    external = [
        make_transaction(
            "X-2001",
            "2026-09-01T10:00:00",
            instrument="ETH",
        )
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert len(results) == 2

    our_result = next(
        result
        for result in results
        if result.status
        == ReconciliationStatus.UNMATCHED_OUR_SIDE
    )

    external_result = next(
        result
        for result in results
        if result.status
        == ReconciliationStatus.UNMATCHED_EXTERNAL_SIDE
    )

    assert our_result.our_transaction.source_reference == "T-1001"
    assert (
        external_result.external_transaction.source_reference
        == "X-2001"
    )


def test_cancelled_transaction_is_excluded():
    ours = [
        make_transaction(
            "T-1018",
            "2026-09-01T10:00:00",
            instrument="SOL",
            quantity="100",
            status=TransactionStatus.CANCELLED,
        )
    ]

    external = [
        make_transaction(
            "X-9008",
            "2026-09-01T10:00:10",
            instrument="SOL",
            quantity="100",
        )
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert any(
        result.status == ReconciliationStatus.EXCLUDED
        for result in results
    )

    assert any(
        result.status
        == ReconciliationStatus.UNMATCHED_EXTERNAL_SIDE
        for result in results
    )


def test_multiple_candidates_require_human_review():
    ours = [
        make_transaction(
            "T-1001",
            "2026-09-01T10:00:00",
        )
    ]

    external = [
        make_transaction(
            "X-2001",
            "2026-09-01T10:00:10",
        ),
        make_transaction(
            "X-2002",
            "2026-09-01T10:00:20",
        ),
    ]

    results = reconcile(
        ours,
        external,
        default_rules(),
    )

    assert len(results) == 3

    review_result = next(
        result
        for result in results
        if result.status == ReconciliationStatus.NEEDS_REVIEW
    )

    assert len(review_result.candidates) == 2