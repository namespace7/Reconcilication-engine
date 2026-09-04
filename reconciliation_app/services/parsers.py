import csv
import io


OUR_COLUMNS = {
    "trade_id": "reference",
    "traded_at": "timestamp",
    "instrument": "instrument",
    "side": "side",
    "quantity": "quantity",
    "price": "unit_price",
    "gross_amount": "amount",
    "state": "status",
}


EXTERNAL_COLUMNS = {
    "reference": "reference",
    "executed_at": "timestamp",
    "symbol": "instrument",
    "direction": "side",
    "qty": "quantity",
    "unit_price": "unit_price",
    "total": "amount",
    "status": "status",
}


def parse_csv(file_bytes: bytes) -> list[dict]:
    text = file_bytes.decode("utf-8")

    reader = csv.DictReader(io.StringIO(text))

    return list(reader)


def normalize_columns(
    row: dict,
    column_mapping: dict,
) -> dict:
    return {
        canonical_name: row[source_name]
        for source_name, canonical_name in column_mapping.items()
    }


def parse_source_file(
    file_bytes: bytes,
    source_type: str,
) -> list[dict]:
    rows = parse_csv(file_bytes)

    if source_type == "OUR_LEDGER":
        mapping = OUR_COLUMNS
    elif source_type == "EXTERNAL_STATEMENT":
        mapping = EXTERNAL_COLUMNS
    else:
        raise ValueError(
            f"Unsupported source type: {source_type}"
        )

    return [
        normalize_columns(row, mapping)
        for row in rows
    ]