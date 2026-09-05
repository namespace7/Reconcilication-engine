import io

from django.test import TestCase
from rest_framework.test import APIClient
from decimal import Decimal


from .models import Source, File, RuleSet, ReconciliationRun
from .services.file_ingestion import ingest_file

class FileUploadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.our_source = Source.objects.create(
            name="Our System",
            source_type="OUR_LEDGER",
        )

    def test_upload_file(self):
        csv_content = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        response = self.client.post(
            "/api/files/",
            {
                "source_id": self.our_source.id,
                "file": io.BytesIO(csv_content.encode("utf-8")),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "CREATED")
        self.assertEqual(response.data["versions_created"], 1)

    def test_upload_same_file_returns_duplicate(self):
        csv_content = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        first_response = self.client.post(
            "/api/files/",
            {
                "source_id": self.our_source.id,
                "file": io.BytesIO(csv_content.encode("utf-8")),
            },
            format="multipart",
        )

        second_response = self.client.post(
            "/api/files/",
            {
                "source_id": self.our_source.id,
                "file": io.BytesIO(csv_content.encode("utf-8")),
            },
            format="multipart",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["status"], "DUPLICATE")
        self.assertEqual(second_response.data["versions_created"], 0)


class ReconciliationRunApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.our_source = Source.objects.create(
            name="Our System",
            source_type="OUR_LEDGER",
        )

        self.external_source = Source.objects.create(
            name="External System",
            source_type="EXTERNAL_STATEMENT",
        )

        self.ruleset = RuleSet.objects.create(
            name="Default",
            version=1,
            amount_tolerance=Decimal("10"),
            price_tolerance=Decimal("5"),
            quantity_tolerance=Decimal("0"),
            time_tolerance_seconds=60,
        )

    def create_our_file(self):
        csv_content = (
            "trade_id,traded_at,instrument,side,quantity,price,"
            "gross_amount,state\n"
            "T-1001,2026-09-01T10:00:00+00:00,BTC,BUY,0.5,"
            "62000,31000,SETTLED\n"
        )

        result = ingest_file(
            source=self.our_source,
            filename="our.csv",
            file_bytes=csv_content.encode("utf-8"),
        )

        return result["file"]

    def create_external_file(self):
        csv_content = (
            "reference,executed_at,symbol,direction,qty,unit_price,"
            "total,status\n"
            "T-1001,2026-09-01T10:00:10+00:00,BTC,B,0.5,"
            "62000,31000,SETTLED\n"
        )

        result = ingest_file(
            source=self.external_source,
            filename="external.csv",
            file_bytes=csv_content.encode("utf-8"),
        )

        return result["file"]

    def test_create_reconciliation_run(self):
        our_file = self.create_our_file()
        external_file = self.create_external_file()

        response = self.client.post(
            "/api/runs/",
            {
                "our_file_id": our_file.id,
                "external_file_id": external_file.id,
                "ruleset_id": self.ruleset.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "COMPLETED")

        run = ReconciliationRun.objects.get(id=response.data["id"])

        self.assertEqual(run.our_file_id, our_file.id)
        self.assertEqual(run.external_file_id, external_file.id)
        self.assertEqual(run.ruleset_id, self.ruleset.id)

        self.assertEqual(run.results.count(), 1)

        result = run.results.first()

        self.assertEqual(
            result.status,
            "MATCHED_WITH_DIFFERENCES",
        )

    def test_create_run_requires_file_ids_and_ruleset(self):
        response = self.client.post(
            "/api/runs/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["error"],
            "our_file_id is required",
        )

    def test_create_run_returns_404_for_missing_file(self):
        response = self.client.post(
            "/api/runs/",
            {
                "our_file_id": 99999,
                "external_file_id": 99998,
                "ruleset_id": self.ruleset.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["error"],
            "Our file not found",
        )

    def test_get_reconciliation_run_returns_results_and_summary(self):
        our_file = self.create_our_file()
        external_file = self.create_external_file()

        create_response = self.client.post(
            "/api/runs/",
            {
                "our_file_id": our_file.id,
                "external_file_id": external_file.id,
                "ruleset_id": self.ruleset.id,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)

        run_id = create_response.data["id"]

        response = self.client.get(f"/api/runs/{run_id}/")

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.data["id"], run_id)
        self.assertEqual(response.data["status"], "COMPLETED")

        self.assertEqual(
            response.data["summary"]["MATCHED_WITH_DIFFERENCES"],
            1,
        )

        self.assertEqual(len(response.data["results"]), 1)

        result = response.data["results"][0]

        self.assertEqual(
            result["status"],
            "MATCHED_WITH_DIFFERENCES",
        )

        self.assertEqual(
            result["our_transaction"]["source_reference"],
            "T-1001",
        )

        self.assertEqual(
            result["external_transaction"]["source_reference"],
            "T-1001",
        )

        self.assertEqual(
            result["differences"][0]["field"],
            "timestamp",
        )


