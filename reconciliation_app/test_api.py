import io

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Source


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
