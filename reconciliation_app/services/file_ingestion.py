import hashlib

from django.db import transaction as db_transaction

from .parsers import parse_source_file
from .transaction_loader import load_transactions

from ..models import File


def calculate_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def ingest_file(
    source,
    filename: str,
    file_bytes: bytes,
):
    file_hash = calculate_file_hash(file_bytes)

    with db_transaction.atomic():

        existing_file = File.objects.filter(
            source=source,
            file_hash=file_hash,
        ).first()

        if existing_file:
            return {
                "status": "DUPLICATE",
                "file": existing_file,
                "versions": [],
            }

        file = File.objects.create(
            source=source,
            filename=filename,
            file_hash=file_hash,
        )

        normalized_rows = parse_source_file(
            file_bytes,
            source.source_type,
        )

        versions = load_transactions(
            file,
            normalized_rows,
        )

        return {
            "status": "CREATED",
            "file": file,
            "versions": versions,
        }