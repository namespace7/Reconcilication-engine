from datetime import datetime
from decimal import Decimal

from reconciliation.comparison import compare_transactions
from reconciliation.domain import (
    CanonicalTransaction,
    Side,
    TransactionStatus,
)
from reconciliation.rules import ReconciliationRules


def make_transaction(
    reference: str,
    timestamp: str,
    quantity: str = "10",
    price: str = "3400",
    amount: str = "34000",
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source_reference=reference,
        timestamp=datetime.fromisoformat(timestamp),
        instrument="ETH",
        side=Side.BUY,
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


def test_identical_transactions_have_no_differences():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:00",
    )

    result = compare_transactions(
        ours,
        external,
        default_rules(),
    )

    assert result.differences == ()
    assert result.has_discrepancies is False


def test_small_differences_are_within_tolerance():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
        price="3400",
        amount="34000",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:30",
        price="3403",
        amount="34005",
    )

    result = compare_transactions(
        ours,
        external,
        default_rules(),
    )

    assert len(result.differences) == 3
    assert all(
        difference.within_tolerance
        for difference in result.differences
    )
    assert result.has_discrepancies is False


def test_large_price_and_amount_differences_are_discrepancies():
    ours = make_transaction(
        "T-1011",
        "2026-09-01T10:00:00",
        price="3400",
        amount="34000",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:30",
        price="3417",
        amount="34170",
    )

    result = compare_transactions(
        ours,
        external,
        default_rules(),
    )

    assert len(result.differences) == 3

    price_difference = next(
        difference
        for difference in result.differences
        if difference.field == "unit_price"
    )

    amount_difference = next(
        difference
        for difference in result.differences
        if difference.field == "amount"
    )

    assert price_difference.difference == Decimal("17")
    assert price_difference.within_tolerance is False

    assert amount_difference.difference == Decimal("170")
    assert amount_difference.within_tolerance is False

    assert result.has_discrepancies is True


def test_quantity_difference_is_reported():
    ours = make_transaction(
        "T-1001",
        "2026-09-01T10:00:00",
        quantity="10",
    )

    external = make_transaction(
        "X-2001",
        "2026-09-01T10:00:10",
        quantity="10.5",
    )

    result = compare_transactions(
        ours,
        external,
        default_rules(),
    )

    quantity_difference = next(
        difference
        for difference in result.differences
        if difference.field == "quantity"
    )

    assert quantity_difference.difference == Decimal("0.5")
    assert quantity_difference.within_tolerance is False