from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


from .domain import CanonicalTransaction
from .rules import ReconciliationRules


@dataclass(frozen=True)
class MatchCandidate:
    transaction: CanonicalTransaction
    score: int
    reasons: tuple[str, ...]
    timestamp_difference_seconds: float
    quantity_difference: Decimal


def find_candidates(
    our_transaction: CanonicalTransaction,
    external_transactions: list[CanonicalTransaction],
    rules: ReconciliationRules,
) -> list[MatchCandidate]:
    candidates = []

    for external_transaction in external_transactions:
        candidate = build_candidate(
            our_transaction,
            external_transaction,
            rules,
        )

        if candidate is not None:
            candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.timestamp_difference_seconds,
            candidate.quantity_difference,
        ),
    )


def build_candidate(
    our_transaction: CanonicalTransaction,
    external_transaction: CanonicalTransaction,
    rules: ReconciliationRules,
) -> Optional[MatchCandidate]:
    if our_transaction.instrument != external_transaction.instrument:
        return None

    if our_transaction.side != external_transaction.side:
        return None

    quantity_difference = abs(
        our_transaction.quantity - external_transaction.quantity
    )

    if quantity_difference > rules.quantity_tolerance:
        return None

    timestamp_difference = abs(
        our_transaction.timestamp - external_transaction.timestamp
    )

    timestamp_difference_seconds = timestamp_difference.total_seconds()

    if timestamp_difference_seconds > rules.time_tolerance_seconds:
        return None

    score = calculate_score(
        our_transaction,
        external_transaction,
        timestamp_difference_seconds,
        quantity_difference,
        rules,
    )

    reasons = build_reasons(
        our_transaction,
        external_transaction,
        timestamp_difference_seconds,
        quantity_difference,
    )

    return MatchCandidate(
        transaction=external_transaction,
        score=score,
        reasons=tuple(reasons),
        timestamp_difference_seconds=timestamp_difference_seconds,
        quantity_difference=quantity_difference,
    )


def calculate_score(
    our_transaction: CanonicalTransaction,
    external_transaction: CanonicalTransaction,
    timestamp_difference_seconds: float,
    quantity_difference: Decimal,
    rules: ReconciliationRules,
) -> int:
    score = 0

    # Source reference is a strong signal when both systems use
    # the same reference format/value.
    if (
        our_transaction.source_reference
        == external_transaction.source_reference
    ):
        score += 50

    # Strong identity signals.
    if our_transaction.instrument == external_transaction.instrument:
        score += 30

    if our_transaction.side == external_transaction.side:
        score += 20

    if quantity_difference == Decimal("0"):
        score += 15
    else:
        score += 5

    # Closer timestamps rank higher.
    if rules.time_tolerance_seconds > 0:
        closeness = 1 - (
            timestamp_difference_seconds
            / rules.time_tolerance_seconds
        )
        score += max(0, round(closeness * 10))
    else:
        score += 10

    return score

def build_reasons(
    our_transaction: CanonicalTransaction,
    external_transaction: CanonicalTransaction,
    timestamp_difference_seconds: float,
    quantity_difference: Decimal,
) -> list[str]:
    reasons = []

    if (
        our_transaction.source_reference
        == external_transaction.source_reference
    ):
        reasons.append("source reference matches")

    if our_transaction.instrument == external_transaction.instrument:
        reasons.append("instrument matches")

    if our_transaction.side == external_transaction.side:
        reasons.append("side matches")

    if quantity_difference == Decimal("0"):
        reasons.append("quantity matches")
    else:
        reasons.append(
            f"quantity difference is {quantity_difference}"
        )

    reasons.append(
        "timestamp difference is "
        f"{timestamp_difference_seconds:g} seconds"
    )

    return reasons