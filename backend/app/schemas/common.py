import datetime as dt
from typing import Literal

from pydantic import Field

from app.utils.money import MAX_AMOUNT_PAISE

Category = Literal[
    "food", "rent", "transportation", "shopping", "entertainment",
    "education", "subscriptions", "personal_care", "other",
]
CATEGORIES: tuple[str, ...] = Category.__args__

PaymentMethod = Literal["upi", "cash", "card", "net_banking", "wallet", "other"]

# A positive amount in integer paise.
PositivePaise = Field(gt=0, le=MAX_AMOUNT_PAISE, description="Amount in integer paise (₹1 = 100)")

# How far back records may be dated.
MAX_PAST_DAYS = 3 * 365


def check_not_future(value: dt.date, today: dt.date) -> dt.date:
    if value > today:
        raise ValueError("Date cannot be in the future")
    if (today - value).days > MAX_PAST_DAYS:
        raise ValueError("Date is too far in the past")
    return value
