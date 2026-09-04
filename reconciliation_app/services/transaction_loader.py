from django.db import transaction as db_transaction

from reconciliation.normalize import normalize_record

from ..models import File, Transaction, TransactionVersion


def load_transactions(
    file: File,
    normalized_rows: list[dict],
) -> list[TransactionVersion]:
    created_versions = []

    for row in normalized_rows:
        canonical = normalize_record(row)

        transaction, created = Transaction.objects.get_or_create(
            source=file.source,
            source_reference=canonical.source_reference,
        )

        if transaction.versions.exists():
            latest_version = transaction.versions.order_by(
                "-version_number"
            ).first()

            version_number = latest_version.version_number + 1
        else:
            version_number = 1

        version = TransactionVersion.objects.create(
            transaction=transaction,
            file=file,
            version_number=version_number,
            timestamp=canonical.timestamp,
            instrument=canonical.instrument,
            side=canonical.side.value,
            quantity=canonical.quantity,
            unit_price=canonical.unit_price,
            amount=canonical.amount,
            status=canonical.status.value,
        )

        transaction.current_version = version
        transaction.save(
            update_fields=["current_version"]
        )

        created_versions.append(version)

    return created_versions