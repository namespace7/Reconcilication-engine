from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .domain import CanonicalTransaction
from .rules import ReconciliationRules


@dataclass(frozen=True)
class FieldDifference:
    field: str
    our_value: object
    external_value: object
    difference: object
    tolerance: object
    within_tolerance: bool


@dataclass(frozen=True)
class ComparisonResult:
    differences: tuple[FieldDifference, ...]

    @property
    def has_discrepancies(self) -> bool:
        return any(
            not difference.within_tolerance
            for difference in self.differences
        )


def compare_transactions(
    our_transaction: CanonicalTransaction,
    external_transaction: CanonicalTransaction,
    rules: ReconciliationRules,
) -> ComparisonResult:
    differences = []

    compare_quantity(
        our_transaction,
        external_transaction,
        rules,
        differences,
    )

    compare_price(
        our_transaction,
        external_transaction,
        rules,
        differences,
    )

    compare_amount(
        our_transaction,
        external_transaction,
        rules,
        differences,
    )

    compare_timestamp(
        our_transaction,
        external_transaction,
        rules,
        differences,
    )

    return ComparisonResult(
        differences=tuple(differences),
    )


def compare_quantity(
    ours: CanonicalTransaction,
    external: CanonicalTransaction,
    rules: ReconciliationRules,
    differences: list[FieldDifference],
) -> None:
    difference = abs(ours.quantity - external.quantity)

    if difference != Decimal("0"):
        differences.append(
            FieldDifference(
                field="quantity",
                our_value=ours.quantity,
                external_value=external.quantity,
                difference=difference,
                tolerance=rules.quantity_tolerance,
                within_tolerance=(
                    difference <= rules.quantity_tolerance
                ),
            )
        )


def compare_price(
    ours: CanonicalTransaction,
    external: CanonicalTransaction,
    rules: ReconciliationRules,
    differences: list[FieldDifference],
) -> None:
    difference = abs(ours.unit_price - external.unit_price)

    if difference != Decimal("0"):
        differences.append(
            FieldDifference(
                field="unit_price",
                our_value=ours.unit_price,
                external_value=external.unit_price,
                difference=difference,
                tolerance=rules.price_tolerance,
                within_tolerance=(
                    difference <= rules.price_tolerance
                ),
            )
        )


def compare_amount(
    ours: CanonicalTransaction,
    external: CanonicalTransaction,
    rules: ReconciliationRules,
    differences: list[FieldDifference],
) -> None:
    difference = abs(ours.amount - external.amount)

    if difference != Decimal("0"):
        differences.append(
            FieldDifference(
                field="amount",
                our_value=ours.amount,
                external_value=external.amount,
                difference=difference,
                tolerance=rules.amount_tolerance,
                within_tolerance=(
                    difference <= rules.amount_tolerance
                ),
            )
        )


def compare_timestamp(
    ours: CanonicalTransaction,
    external: CanonicalTransaction,
    rules: ReconciliationRules,
    differences: list[FieldDifference],
) -> None:
    difference = abs(
        ours.timestamp - external.timestamp
    )

    difference_seconds = difference.total_seconds()

    if difference_seconds != 0:
        differences.append(
            FieldDifference(
                field="timestamp",
                our_value=ours.timestamp,
                external_value=external.timestamp,
                difference=difference_seconds,
                tolerance=rules.time_tolerance_seconds,
                within_tolerance=(
                    difference_seconds
                    <= rules.time_tolerance_seconds
                ),
            )
        )

