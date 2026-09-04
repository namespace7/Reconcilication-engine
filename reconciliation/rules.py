from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class ReconciliationRules:
    time_tolerance_seconds: int
    quantity_tolerance: Decimal
    price_tolerance: Decimal
    amount_tolerance: Decimal
