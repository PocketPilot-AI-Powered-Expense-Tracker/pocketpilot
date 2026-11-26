import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Category, PaymentMethod, PositivePaise, check_not_future
from app.utils import dates


class ExpenseIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount_paise: int = PositivePaise
    category: Category
    description: str = Field(min_length=1, max_length=120)
    date: dt.date
    payment_method: PaymentMethod = "upi"
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def not_future(cls, v: dt.date) -> dt.date:
        return check_not_future(v, dates.app_today())

    @field_validator("notes")
    @classmethod
    def empty_notes_to_none(cls, v):
        return v or None


class ExpenseOut(BaseModel):
    id: str
    amount_paise: int
    category: Category
    description: str
    date: dt.date
    payment_method: PaymentMethod
    notes: str | None = None
    # manual = typed by the user, routine = a planned occurrence marked spent,
    # upi_review = an accepted pending UPI transaction (Phase 3),
    # opening = money spent earlier this month, entered on the Budget page
    source: Literal["manual", "routine", "upi_review", "opening"] = "manual"
    occurrence_id: str | None = None
    pending_id: str | None = None
    auto_deducted: bool = False
    created_at: dt.datetime
    updated_at: dt.datetime


class ExpenseList(BaseModel):
    items: list[ExpenseOut]
    total: int
    total_amount_paise: int
