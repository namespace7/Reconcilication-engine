from decimal import Decimal

from django.test import TestCase

from .models import (
    File,
    Source,
    Transaction,
    TransactionVersion,
)
from .services.file_ingestion import ingest_file


class FileIngestionTests(TestCase):

    def setUp(self):
        self.source = Source.objects.create(
            name="Our Ledger",
            source_type="OUR_LEDGER",
        )

    def test_ingests_new_file_and_creates_transaction_version(self):
        csv_data = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,62000,"
            "31000,SETTLED\n"
        ).encode("utf-8")

        result = ingest_file(
            self.source,
            "ledger.csv",
            csv_data,
        )

        assert result["status"] == "CREATED"
        assert File.objects.count() == 1
        assert Transaction.objects.count() == 1
        assert TransactionVersion.objects.count() == 1

        transaction = Transaction.objects.get(
            source=self.source,
            source_reference="T-1001",
        )

        version = transaction.current_version

        assert version is not None
        assert version.version_number == 1
        assert version.instrument == "BTC"
        assert version.side == "BUY"
        assert version.quantity == Decimal("0.5")
        assert version.unit_price == Decimal("62000")
        assert version.amount == Decimal("31000")

    def test_same_file_is_detected_as_duplicate(self):
        csv_data = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,62000,"
            "31000,SETTLED\n"
        ).encode("utf-8")

        first_result = ingest_file(
            self.source,
            "ledger.csv",
            csv_data,
        )

        second_result = ingest_file(
            self.source,
            "ledger-copy.csv",
            csv_data,
        )

        assert first_result["status"] == "CREATED"
        assert second_result["status"] == "DUPLICATE"

        assert File.objects.count() == 1
        assert Transaction.objects.count() == 1
        assert TransactionVersion.objects.count() == 1

    def test_correction_creates_new_version_and_preserves_history(self):
        original_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,62000,"
            "31000,SETTLED\n"
        ).encode("utf-8")

        correction_csv = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,62100,"
            "31050,SETTLED\n"
        ).encode("utf-8")

        ingest_file(
            self.source,
            "ledger-original.csv",
            original_csv,
        )

        ingest_file(
            self.source,
            "ledger-correction.csv",
            correction_csv,
        )

        assert File.objects.count() == 2
        assert Transaction.objects.count() == 1
        assert TransactionVersion.objects.count() == 2

        transaction = Transaction.objects.get(
            source=self.source,
            source_reference="T-1001",
        )

        versions = list(
            transaction.versions.order_by("version_number")
        )

        assert versions[0].version_number == 1
        assert versions[0].unit_price == Decimal("62000")

        assert versions[1].version_number == 2
        assert versions[1].unit_price == Decimal("62100")

        assert transaction.current_version == versions[1]