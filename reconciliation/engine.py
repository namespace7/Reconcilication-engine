from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .comparison import ComparisonResult, compare_transactions
from .domain import CanonicalTransaction, TransactionStatus
from .matching import MatchCandidate, find_candidates
from .rules import ReconciliationRules


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    MATCHED_WITH_DIFFERENCES = "MATCHED_WITH_DIFFERENCES"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    UNMATCHED_OUR_SIDE = "UNMATCHED_OUR_SIDE"
    UNMATCHED_EXTERNAL_SIDE = "UNMATCHED_EXTERNAL_SIDE"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    our_transaction: Optional[CanonicalTransaction]
    external_transaction: Optional[CanonicalTransaction]
    comparison: Optional[ComparisonResult]
    candidates: tuple
    match_method: Optional[str] = None


def reconcile(
    our_transactions: List[CanonicalTransaction],
    external_transactions: List[CanonicalTransaction],
    rules: ReconciliationRules,
) -> List[ReconciliationResult]:
    results = []

    available_external = [
        transaction
        for transaction in external_transactions
        if transaction.status != TransactionStatus.CANCELLED
    ]

    matched_external_references = set()

    for our_transaction in our_transactions:

        # Cancelled transactions are excluded from comparison.
        if our_transaction.status == TransactionStatus.CANCELLED:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.EXCLUDED,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=(),
                    match_method=None,
                )
            )
            continue

        # Don't offer an external transaction that has already
        # been paired during this reconciliation run.
        available = [
            transaction
            for transaction in available_external
            if transaction.source_reference
            not in matched_external_references
        ]

        candidates = find_candidates(
            our_transaction,
            available,
            rules,
        )

        if not candidates:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.UNMATCHED_OUR_SIDE,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=(),
                    match_method=None,
                )
            )
            continue

        selected_candidate = select_candidate(
            our_transaction,
            candidates,
        )

        if selected_candidate is None:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.NEEDS_REVIEW,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=tuple(candidates),
                    match_method=None,
                )
            )
            continue

        external_transaction = selected_candidate.transaction

        matched_external_references.add(
            external_transaction.source_reference
        )

        comparison = compare_transactions(
            our_transaction,
            external_transaction,
            rules,
        )

        status = determine_status(comparison)

        results.append(
            ReconciliationResult(
                status=status,
                our_transaction=our_transaction,
                external_transaction=external_transaction,
                comparison=comparison,
                candidates=(selected_candidate,),
                match_method="exact_reference"
                if (
                    our_transaction.source_reference
                    == external_transaction.source_reference
                )
                else "attribute_match",
            )
        )

    # Anything that wasn't paired is unmatched on the external side.
    for external_transaction in available_external:
        if (
            external_transaction.source_reference
            not in matched_external_references
        ):
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.UNMATCHED_EXTERNAL_SIDE,
                    our_transaction=None,
                    external_transaction=external_transaction,
                    comparison=None,
                    candidates=(),
                    match_method=None,
                )
            )

    return results


def select_candidate(
    our_transaction: CanonicalTransaction,
    candidates: List[MatchCandidate],
) -> Optional[MatchCandidate]:
    exact_reference_candidates = [
        candidate
        for candidate in candidates
        if (
            candidate.transaction.source_reference
            == our_transaction.source_reference
        )
    ]

    # A unique exact reference is a strong enough signal
    # to select automatically.
    if len(exact_reference_candidates) == 1:
        return exact_reference_candidates[0]

    # A single candidate is also safe to select.
    if len(candidates) == 1:
        return candidates[0]

    # Multiple plausible candidates without a unique strong
    # identity signal require human review.
    return None


def determine_status(
    comparison: ComparisonResult,
) -> ReconciliationStatus:
    if not comparison.differences:
        return ReconciliationStatus.MATCHED

    if comparison.has_discrepancies:
        return ReconciliationStatus.NEEDS_REVIEW

    return ReconciliationStatus.MATCHED_WITH_DIFFERENCES