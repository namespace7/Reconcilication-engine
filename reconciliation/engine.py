# reconciliation/engine.py

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

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
    candidates: Tuple[MatchCandidate, ...]
    match_method: Optional[str] = None


def reconcile(
    our_transactions: List[CanonicalTransaction],
    external_transactions: List[CanonicalTransaction],
    rules: ReconciliationRules,
    manual_matches: Optional[Dict[str, str]] = None,
) -> List[ReconciliationResult]:
    """
    Reconcile transactions from our system against an external system.

    manual_matches maps:
        our_source_reference -> external_source_reference

    Manual matches are applied before automatic candidate matching.
    This allows a human decision from a previous run to override
    automatic matching in future runs.
    """

    if manual_matches is None:
        manual_matches = {}

    # Cancelled transactions are excluded from reconciliation.
    available_external = [
        transaction
        for transaction in external_transactions
        if transaction.status != TransactionStatus.CANCELLED
    ]

    matched_external_references = set()

    results = []

    for our_transaction in our_transactions:

        # Cancelled transactions on our side are excluded as well.
        if our_transaction.status == TransactionStatus.CANCELLED:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.EXCLUDED,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=(),
                )
            )
            continue

        # Only consider external transactions that have not already
        # been paired in this reconciliation run.
        available = [
            transaction
            for transaction in available_external
            if transaction.source_reference not in matched_external_references
        ]

        # ---------------------------------------------------------
        # 1. Apply persisted manual match first
        # ---------------------------------------------------------

        manual_external_reference = manual_matches.get(
            our_transaction.source_reference
        )

        if manual_external_reference:
            manual_candidate = next(
                (
                    transaction
                    for transaction in available
                    if transaction.source_reference == manual_external_reference
                ),
                None,
            )

            if manual_candidate is not None:
                comparison = compare_transactions(
                    our_transaction,
                    manual_candidate,
                    rules,
                )

                matched_external_references.add(
                    manual_candidate.source_reference
                )

                results.append(
                    ReconciliationResult(
                        status=determine_status(comparison),
                        our_transaction=our_transaction,
                        external_transaction=manual_candidate,
                        comparison=comparison,
                        candidates=(),
                        match_method="manual",
                    )
                )

                # Do not run automatic matching for this transaction.
                continue

        # ---------------------------------------------------------
        # 2. Automatic candidate matching
        # ---------------------------------------------------------

        candidates = find_candidates(
            our_transaction,
            available,
            rules,
        )

        # No plausible external transaction.
        if not candidates:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.UNMATCHED_OUR_SIDE,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=(),
                )
            )
            continue

        # ---------------------------------------------------------
        # 3. Select automatic candidate
        # ---------------------------------------------------------

        selected_candidate = select_candidate(
            our_transaction,
            candidates,
        )

        # Multiple plausible candidates and no deterministic
        # reason to choose one -> human review.
        if selected_candidate is None:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.NEEDS_REVIEW,
                    our_transaction=our_transaction,
                    external_transaction=None,
                    comparison=None,
                    candidates=tuple(candidates),
                )
            )
            continue

        external_transaction = selected_candidate.transaction

        matched_external_references.add(
            external_transaction.source_reference
        )

        # ---------------------------------------------------------
        # 4. Compare the matched transactions
        # ---------------------------------------------------------

        comparison = compare_transactions(
            our_transaction,
            external_transaction,
            rules,
        )

        results.append(
            ReconciliationResult(
                status=determine_status(comparison),
                our_transaction=our_transaction,
                external_transaction=external_transaction,
                comparison=comparison,
                candidates=tuple(candidates),
                match_method=(
                    "exact_reference"
                    if our_transaction.source_reference
                    == external_transaction.source_reference
                    else "attribute_match"
                ),
            )
        )

    # -------------------------------------------------------------
    # 5. Find external transactions that were never matched
    # -------------------------------------------------------------

    for external_transaction in available_external:
        if external_transaction.source_reference not in matched_external_references:
            results.append(
                ReconciliationResult(
                    status=ReconciliationStatus.UNMATCHED_EXTERNAL_SIDE,
                    our_transaction=None,
                    external_transaction=external_transaction,
                    comparison=None,
                    candidates=(),
                )
            )

    return results


def select_candidate(
    our_transaction: CanonicalTransaction,
    candidates: List[MatchCandidate],
) -> Optional[MatchCandidate]:
    """
    Select an automatic candidate only when the decision is
    deterministic.

    Rules:
    - A unique exact source-reference match wins.
    - A single plausible candidate wins.
    - Multiple plausible candidates require human review.
    """

    exact_reference_candidates = [
        candidate
        for candidate in candidates
        if candidate.transaction.source_reference
        == our_transaction.source_reference
    ]

    if len(exact_reference_candidates) == 1:
        return exact_reference_candidates[0]

    if len(candidates) == 1:
        return candidates[0]

    return None


def determine_status(
    comparison: ComparisonResult,
) -> ReconciliationStatus:
    """
    Convert field-level comparison results into a reconciliation status.
    """

    if not comparison.differences:
        return ReconciliationStatus.MATCHED

    if comparison.has_discrepancies:
        return ReconciliationStatus.NEEDS_REVIEW

    return ReconciliationStatus.MATCHED_WITH_DIFFERENCES