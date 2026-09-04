from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class TransactionStatus(str, Enum):
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"

@dataclass(frozen=True)
class CanonicalTransaction:
    source_reference: str
    timestamp: datetime
    instrument: str
    side: Side
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    status: TransactionStatus


