from django.db import IntegrityError
from django.test import TestCase

from .models import File, Source


class FileIngestionTests(TestCase):

    def test_same_file_hash_cannot_be_uploaded_twice_for_same_source(self):
        source = Source.objects.create(
            name="External Statement",
            source_type="CSV",
        )

        File.objects.create(
            source=source,
            filename="statement.csv",
            file_hash="abc123",
        )

        with self.assertRaises(IntegrityError):
            File.objects.create(
                source=source,
                filename="statement-copy.csv",
                file_hash="abc123",
            )