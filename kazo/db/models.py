from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class Expense:
    id: int | None
    chat_id: int
    user_id: int
    store: str | None
    amount: float
    original_currency: str
    amount_eur: float
    exchange_rate: float
    category: str | None
    items_json: str | None
    source: str
    expense_date: date
    note: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class ExpenseItem:
    id: int | None
    expense_id: int
    name: str
    price: float
    currency: str
    quantity: float = 1.0


@dataclass(slots=True)
class Budget:
    id: int | None
    chat_id: int
    category: str | None
    amount_eur: float


@dataclass(slots=True)
class Subscription:
    id: int | None
    chat_id: int
    name: str
    amount: float
    original_currency: str
    amount_eur: float
    frequency: str = "monthly"
    category: str | None = None
    billing_day: int | None = None
    active: bool = True
    created_at: datetime | None = None
