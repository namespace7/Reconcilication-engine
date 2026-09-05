from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from .models import (
    File,
    ManualDecision,
    ReconciliationResult,
    ReconciliationRun,
    RuleSet,
    Source,
    Transaction,
    TransactionVersion,
)
from .services.file_ingestion import ingest_file
from .services.reconciliation_service import run_reconciliation



class ReconciliationServiceTests(TestCase):

    def setUp(self):
        self.our_source = Source.objects.create(
            name="Our Ledger",
            source_type="OUR_LEDGER",
        )

        self.external_source = Source.objects.create(
            name="External Statement",
            source_type="EXTERNAL_STATEMENT",
        )

        self.ruleset = RuleSet.objects.create(
            name="default",
            version=1,
            amount_tolerance=Decimal("10"),
            price_tolerance=Decimal("5"),
            quantity_tolerance=Decimal("0"),
            time_tolerance_seconds=60,
        )

    def ingest_our_file(self, csv_data, filename="our.csv"):
        result = ingest_file(
            self.our_source,
            filename,
            csv_data.encode("utf-8"),
        )
        return result["file"]

    def ingest_external_file(
        self,
        csv_data,
        filename="external.csv",
    ):
        result = ingest_file(
            self.external_source,
            filename,
            csv_data.encode("utf-8"),
        )
        return result["file"]

    def test_identical_transactions_are_matched(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(
            external_csv
        )

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        self.assertEqual(
            run.status,
            ReconciliationRun.Status.COMPLETED,
        )

        result = run.results.get()

        self.assertEqual(
            result.status,
            ReconciliationResult.Status.MATCHED,
        )

        self.assertEqual(
            result.match_method,
            "exact_reference",
        )

        self.assertIsNotNone(result.our_version)
        self.assertIsNotNone(result.external_version)

        self.assertEqual(
            result.differences_json,
            [],
        )

    def test_small_difference_is_persisted_as_within_tolerance(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:30+00:00,BTC,B,0.5,"
            "62003,31005,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(
            external_csv
        )

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        self.assertEqual(
            result.status,
            ReconciliationResult.Status.MATCHED_WITH_DIFFERENCES,
        )

        self.assertEqual(len(result.differences_json), 3)

        fields = {
            difference["field"]
            for difference in result.differences_json
        }

        self.assertEqual(
            fields,
            {"unit_price", "amount", "timestamp"},
        )

        for difference in result.differences_json:
            self.assertTrue(
                difference["within_tolerance"]
            )

    def test_large_difference_requires_review(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,B,0.5,"
            "62100,31100,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(
            external_csv
        )

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        self.assertEqual(
            result.status,
            ReconciliationResult.Status.NEEDS_REVIEW,
        )

        self.assertTrue(result.differences_json)

        price_difference = next(
            difference
            for difference in result.differences_json
            if difference["field"] == "unit_price"
        )

        self.assertEqual(
            Decimal(price_difference["difference"]),
            Decimal("100"),
        )

        self.assertFalse(
            price_difference["within_tolerance"]
        )

    def test_attribute_match_works_when_references_differ(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1015,2026-09-01T10:00:00+00:00,SOL,SELL,300,"
            "146,43800,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-9001,2026-09-01T10:00:20+00:00,SOL,S,300,"
            "146,43800,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(
            external_csv
        )

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        self.assertEqual(
            result.status,
            ReconciliationResult.Status.MATCHED_WITH_DIFFERENCES,
        )

        self.assertEqual(
            result.match_method,
            "attribute_match",
        )

        self.assertEqual(
            result.external_version
            .transaction
            .source_reference,
            "C-9001",
        )

    def test_reconciliation_uses_versions_from_selected_files(self):
        original_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        correction_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62100,31050,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
        )

        original_file = self.ingest_our_file(
            original_csv,
            "original.csv",
        )

        correction_file = self.ingest_our_file(
            correction_csv,
            "correction.csv",
        )

        external_file = self.ingest_external_file(
            external_csv,
        )

        transaction = (
            TransactionVersion.objects
            .filter(
                transaction__source=self.our_source,
                transaction__source_reference="T-1001",
            )
            .order_by("-version_number")
            .first()
            .transaction
        )

        self.assertEqual(
            transaction.current_version.unit_price,
            Decimal("62100"),
        )

        run = run_reconciliation(
            original_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        self.assertEqual(
            result.our_version.unit_price,
            Decimal("62000"),
        )

        self.assertEqual(
            result.our_version.version_number,
            1,
        )

        self.assertEqual(
            result.external_version.unit_price,
            Decimal("62000"),
        )

        self.assertNotEqual(
            result.our_version,
            transaction.current_version,
        )

        correction_version = (
            TransactionVersion.objects
            .get(
                transaction=transaction,
                version_number=2,
            )
        )

        self.assertEqual(
            correction_version.file,
            correction_file,
        )

    def test_failed_run_is_persisted_as_failed(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(external_csv)

        with patch(
            "reconciliation_app.services.reconciliation_service.reconcile",
            side_effect=RuntimeError("reconciliation failed"),
        ):
            with self.assertRaises(RuntimeError):
                run_reconciliation(
                    our_file,
                    external_file,
                    self.ruleset,
                )

        run = ReconciliationRun.objects.get()

        self.assertEqual(
            run.status,
            ReconciliationRun.Status.FAILED,
        )
        self.assertIsNotNone(run.completed_at)
        self.assertEqual(run.results.count(), 0)

    def test_manual_match_decision_is_persisted_for_transactions(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1015,2026-09-01T10:00:00+00:00,SOL,SELL,300,"
            "146,43800,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-9001,2026-09-01T10:00:20+00:00,SOL,S,300,"
            "146,43800,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(external_csv)

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        our_transaction = result.our_version.transaction
        external_transaction = result.external_version.transaction

        decision = ManualDecision.objects.create(
            result=result,
            our_transaction=our_transaction,
            external_transaction=external_transaction,
            decision=ManualDecision.Decision.MATCH,
            reason="Confirmed by accounting team",
            decided_by="test-user",
        )

        self.assertEqual(
            decision.decision,
            ManualDecision.Decision.MATCH,
        )

        self.assertEqual(
            decision.our_transaction,
            our_transaction,
        )

        self.assertEqual(
            decision.external_transaction,
            external_transaction,
        )

    def test_manual_decision_survives_transaction_correction(self):
        original_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1015,2026-09-01T10:00:00+00:00,SOL,SELL,300,"
            "146,43800,SETTLED\n"
        )

        correction_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1015,2026-09-01T10:00:00+00:00,SOL,SELL,300,"
            "147,44100,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-9001,2026-09-01T10:00:20+00:00,SOL,S,300,"
            "146,43800,SETTLED\n"
        )

        original_file = self.ingest_our_file(
            original_csv,
            "original.csv",
        )

        correction_file = self.ingest_our_file(
            correction_csv,
            "correction.csv",
        )

        external_file = self.ingest_external_file(
            external_csv,
        )

        first_run = run_reconciliation(
            original_file,
            external_file,
            self.ruleset,
        )

        first_result = first_run.results.get()

        our_transaction = first_result.our_version.transaction
        external_transaction = first_result.external_version.transaction

        ManualDecision.objects.create(
            result=first_result,
            our_transaction=our_transaction,
            external_transaction=external_transaction,
            decision=ManualDecision.Decision.MATCH,
            reason="Confirmed manually",
            decided_by="test-user",
        )

        # The correction creates a new version but keeps the same
        # underlying transaction.
        correction_version = (
            TransactionVersion.objects
            .get(
                transaction=our_transaction,
                file=correction_file,
            )
        )

        self.assertNotEqual(
            correction_version,
            first_result.our_version,
        )

        self.assertEqual(
            correction_version.transaction,
            our_transaction,
        )

        # The human decision still points to the same business
        # transaction pair.
        decision = ManualDecision.objects.get(
            our_transaction=our_transaction,
            external_transaction=external_transaction,
        )

        self.assertEqual(
            decision.decision,
            ManualDecision.Decision.MATCH,
        )

    def test_duplicate_manual_decision_for_same_pair_is_rejected(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1015,2026-09-01T10:00:00+00:00,SOL,SELL,300,"
            "146,43800,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-9001,2026-09-01T10:00:20+00:00,SOL,S,300,"
            "146,43800,SETTLED\n"
        )

        our_file = self.ingest_our_file(our_csv)
        external_file = self.ingest_external_file(external_csv)

        run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        result = run.results.get()

        our_transaction = result.our_version.transaction
        external_transaction = result.external_version.transaction

        ManualDecision.objects.create(
            result=result,
            our_transaction=our_transaction,
            external_transaction=external_transaction,
            decision=ManualDecision.Decision.MATCH,
            reason="First decision",
            decided_by="test-user",
        )

        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ManualDecision.objects.create(
                result=result,
                our_transaction=our_transaction,
                external_transaction=external_transaction,
                decision=ManualDecision.Decision.NO_MATCH,
                reason="Conflicting decision",
                decided_by="another-user",
            )

    def test_future_run_respects_persisted_manual_match(self):
        our_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-2001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-2001,2026-09-01T10:00:10+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
            "C-2002,2026-09-01T10:00:20+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
        )

        our_file = self.ingest_our_file(
            our_csv,
            "our-original.csv",
        )
        external_file = self.ingest_external_file(
            external_csv,
            "external-original.csv",
        )

        first_run = run_reconciliation(
            our_file,
            external_file,
            self.ruleset,
        )

        review_result = first_run.results.get(
            our_version__transaction__source_reference="T-2001",
        )

        self.assertEqual(
            review_result.status,
            ReconciliationResult.Status.NEEDS_REVIEW,
        )

        our_transaction = review_result.our_version.transaction

        external_transaction = Transaction.objects.get(
            source=self.external_source,
            source_reference="C-2002",
        )

        ManualDecision.objects.create(
            result=review_result,
            our_transaction=our_transaction,
            external_transaction=external_transaction,
            decision=ManualDecision.Decision.MATCH,
            reason="Confirmed manually from settlement report",
            decided_by="tester",
        )

        # A correction file creates a new version of C-2002.
        corrected_external_csv = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "C-2001,2026-09-01T10:00:10+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
            "C-2002,2026-09-01T10:00:20+00:00,BTC,B,0.5,"
            "62100,31050,SETTLED\n"
        )

        corrected_external_file = self.ingest_external_file(
            corrected_external_csv,
            "external-correction.csv",
        )

        second_run = run_reconciliation(
            our_file,
            corrected_external_file,
            self.ruleset,
        )

        second_result = second_run.results.get(
            our_version__transaction__source_reference="T-2001",
        )

        self.assertEqual(
            second_result.status,
            ReconciliationResult.Status.NEEDS_REVIEW,
        )

        self.assertEqual(
            second_result.external_version.transaction.source_reference,
            "C-2002",
        )

        self.assertEqual(
            second_result.external_version.version_number,
            2,
        )

        self.assertEqual(
            second_result.match_method,
            "manual",
        )