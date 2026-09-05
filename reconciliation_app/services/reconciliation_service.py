from django.db import transaction as db_transaction
from django.utils import timezone

from reconciliation.domain import (
    CanonicalTransaction,
    Side,
    TransactionStatus,
)
from reconciliation.engine import reconcile
from reconciliation.rules import ReconciliationRules

from ..models import (
    File,
    ManualDecision,
    ReconciliationResult,
    ReconciliationRun,
    RuleSet,
    TransactionVersion,
)


def transaction_version_to_domain(
    version: TransactionVersion,
) -> CanonicalTransaction:
    return CanonicalTransaction(
        source_reference=version.transaction.source_reference,
        timestamp=version.timestamp,
        instrument=version.instrument,
        side=Side(version.side),
        quantity=version.quantity,
        unit_price=version.unit_price,
        amount=version.amount,
        status=TransactionStatus(version.status),
    )


def ruleset_to_domain(
    ruleset: RuleSet,
) -> ReconciliationRules:
    return ReconciliationRules(
        time_tolerance_seconds=ruleset.time_tolerance_seconds,
        quantity_tolerance=ruleset.quantity_tolerance,
        price_tolerance=ruleset.price_tolerance,
        amount_tolerance=ruleset.amount_tolerance,
    )


def run_reconciliation(
    our_file: File,
    external_file: File,
    ruleset: RuleSet,
) -> ReconciliationRun:

    # Create the run first and commit it independently.
    # This means a later failure can be recorded as FAILED
    # instead of rolling back the run itself.
    run = ReconciliationRun.objects.create(
        our_file=our_file,
        external_file=external_file,
        ruleset=ruleset,
        status=ReconciliationRun.Status.RUNNING,
    )

    try:
        # Result creation should be atomic. If anything fails while
        # creating reconciliation results, none of the partial results
        # should remain in the database.
        with db_transaction.atomic():

            # Load the exact versions belonging to the selected files,
            # not the transaction's current_version.
            our_versions = list(
                TransactionVersion.objects
                .filter(file=our_file)
                .select_related("transaction")
            )

            external_versions = list(
                TransactionVersion.objects
                .filter(file=external_file)
                .select_related("transaction")
            )

            our_transaction_ids = {
                version.transaction_id
                for version in our_versions
            }

            external_transaction_ids = {
                version.transaction_id
                for version in external_versions
            }

            manual_decisions = (
                ManualDecision.objects
                .filter(
                    decision=ManualDecision.Decision.MATCH,
                    our_transaction_id__in=our_transaction_ids,
                    external_transaction_id__in=external_transaction_ids,
                )
                .select_related(
                    "our_transaction",
                    "external_transaction",
                )
            )

            manual_matches = {
                decision.our_transaction.source_reference:
                    decision.external_transaction.source_reference
                for decision in manual_decisions
            }

            # Convert DB objects into pure domain objects.
            # Keep an identity mapping so we can map engine results
            # back to the original database versions.
            our_domain_by_id = {}
            our_transactions = []

            for version in our_versions:
                domain_transaction = transaction_version_to_domain(version)
                our_transactions.append(domain_transaction)
                our_domain_by_id[id(domain_transaction)] = version

            external_domain_by_id = {}
            external_transactions = []

            for version in external_versions:
                domain_transaction = transaction_version_to_domain(version)
                external_transactions.append(domain_transaction)
                external_domain_by_id[id(domain_transaction)] = version

            rules = ruleset_to_domain(ruleset)

            engine_results = reconcile(
                our_transactions,
                external_transactions,
                rules,
                manual_matches=manual_matches,
            )

            for engine_result in engine_results:
                our_version = None
                external_version = None

                if engine_result.our_transaction is not None:
                    our_version = our_domain_by_id[
                        id(engine_result.our_transaction)
                    ]

                if engine_result.external_transaction is not None:
                    external_version = external_domain_by_id[
                        id(engine_result.external_transaction)
                    ]

                differences = []

                if engine_result.comparison is not None:
                    differences = [
                        {
                            "field": difference.field,
                            "our_value": str(difference.our_value),
                            "external_value": str(difference.external_value),
                            "difference": str(difference.difference),
                            "tolerance": str(difference.tolerance),
                            "within_tolerance": difference.within_tolerance,
                        }
                        for difference in engine_result.comparison.differences
                    ]

                candidates = [
                                {
                                    "transaction_id": external_domain_by_id[
                                        id(candidate.transaction)
                                    ].transaction_id,
                                    "source_reference": candidate.transaction.source_reference,
                                    "score": candidate.score,
                                    "reasons": candidate.reasons,
                                    "timestamp_difference_seconds": (
                                        candidate.timestamp_difference_seconds
                                    ),
                                    "quantity_difference": str(
                                        candidate.quantity_difference
                                    ),
                                }
                                for candidate in engine_result.candidates
                            ]

                ReconciliationResult.objects.create(
                    run=run,
                    our_version=our_version,
                    external_version=external_version,
                    status=engine_result.status.value,
                    match_method=engine_result.match_method,
                    confidence=None,
                    differences_json=differences,
                    candidates_json=candidates,
                )

        # The atomic block completed successfully.
        run.status = ReconciliationRun.Status.COMPLETED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])

        return run

    except Exception:
        # This update happens outside the result transaction, so the
        # failed run remains visible for inspection/debugging.
        run.status = ReconciliationRun.Status.FAILED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])

        raise