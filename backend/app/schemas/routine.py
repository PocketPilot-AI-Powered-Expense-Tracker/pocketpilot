import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Category, PaymentMethod, PositivePaise
from app.utils.money import MAX_AMOUNT_PAISE

Frequency = Literal["daily", "weekly", "monthly"]
OccurrenceStatus = Literal["planned", "spent", "skipped"]
# auto   = recorded as an expense automatically on each due date (e.g. rent)
# manual = stays planned until the user taps "Spent" (e.g. tea)
DeductionMode = Literal["auto", "manual"]


class RoutineIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)
    amount_paise: int = PositivePaise
    category: Category
    frequency: Frequency
    weekday: int | None = Field(default=None, ge=0, le=6, description="0 = Monday … 6 = Sunday (weekly only)")
    day_of_month: int | None = Field(default=None, ge=1, le=28, description="1–28 (monthly only)")
    start_date: dt.date | None = Field(default=None, description="Defaults to today")
    end_date: dt.date | None = None
    payment_method: PaymentMethod = "upi"
    deduction_mode: DeductionMode = "manual"
    # Only used when CREATING a monthly expense whose due day this month has already passed:
    # also record this month's amount, dated on that due date. Ignored on updates.
    deduct_this_month: bool = False

    @model_validator(mode="after")
    def check_schedule(self):
        if self.frequency == "weekly":
            if self.weekday is None:
                raise ValueError("Choose a day of the week for a weekly routine")
            self.day_of_month = None
        elif self.frequency == "monthly":
            if self.day_of_month is None:
                raise ValueError("Choose a day of the month for a monthly routine")
            self.weekday = None
        else:
            self.weekday = None
            self.day_of_month = None
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("End date must be on or after the start date")
        if self.deduct_this_month and self.frequency != "monthly":
            raise ValueError("'Deduct for this month' is only available for monthly expenses")
        return self


class RoutineOut(BaseModel):
    id: str
    name: str
    amount_paise: int
    category: Category
    frequency: Frequency
    weekday: int | None
    day_of_month: int | None
    start_date: dt.date
    end_date: dt.date | None
    payment_method: PaymentMethod
    deduction_mode: DeductionMode = "manual"
    active: bool
    # Set only in the create response when this month's amount was recorded.
    this_month_expense_id: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class OccurrenceOut(BaseModel):
    id: str
    rule_id: str
    name: str
    amount_paise: int
    category: Category
    scheduled_date: dt.date
    original_date: dt.date
    rescheduled: bool
    status: OccurrenceStatus
    expense_id: str | None = None
    deduction_mode: DeductionMode = "manual"
    auto_deducted: bool = False


class SpendRequest(BaseModel):
    """Optional overrides when marking an occurrence as spent (the real amount may differ)."""
    amount_paise: int | None = Field(default=None, gt=0, le=MAX_AMOUNT_PAISE)
    date: dt.date | None = None
    payment_method: PaymentMethod | None = None


class RescheduleRequest(BaseModel):
    new_date: dt.date


class SpendResult(BaseModel):
    occurrence: OccurrenceOut
    expense_id: str
