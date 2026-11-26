import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import Category, PaymentMethod, PositivePaise
from app.utils import dates
from app.utils.money import MAX_AMOUNT_PAISE

SourceApp = Literal["phonepe", "gpay", "paytm", "bhim", "other"]
PendingStatus = Literal["pending_review", "accepted", "rejected"]


class DetectedTransactionIn(BaseModel):
    """What a detector (the future Android companion app) submits.
    Only parsed fields are sent — never the full notification text."""
    model_config = ConfigDict(str_strip_whitespace=True)

    amount_paise: int = PositivePaise
    source_app: SourceApp
    counterparty: str | None = Field(default=None, max_length=60)
    transaction_ref: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{6,32}$")
    notification_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$",
                                          description="SHA-256 of package + title + text + post time")
    detected_at: dt.datetime

    @field_validator("detected_at")
    @classmethod
    def sensible_time(cls, v: dt.datetime) -> dt.datetime:
        if v.tzinfo is None:
            raise ValueError("detected_at must include a timezone")
        now = dates.utc_now()
        if v > now + dt.timedelta(minutes=10):
            raise ValueError("detected_at is in the future")
        if v < now - dt.timedelta(days=90):
            raise ValueError("detected_at is too old")
        return v

    @model_validator(mode="after")
    def needs_dedupe_key(self):
        if not self.transaction_ref and not self.notification_hash:
            raise ValueError("Provide transaction_ref or notification_hash so duplicates can be detected")
        return self


class SimulatedNotificationIn(BaseModel):
    """A raw notification, used only by the in-app simulator for testing."""
    model_config = ConfigDict(str_strip_whitespace=True)

    source_app: SourceApp
    title: str = Field(default="", max_length=120)
    text: str = Field(min_length=1, max_length=400)
    posted_at: dt.datetime | None = None


class AcceptRequest(BaseModel):
    """Accept a pending transaction. Any field given here overrides the detected
    value ("Edit and add"); omitted fields use the detected/suggested values."""
    model_config = ConfigDict(str_strip_whitespace=True)

    amount_paise: int | None = Field(default=None, gt=0, le=MAX_AMOUNT_PAISE)
    category: Category | None = None
    description: str | None = Field(default=None, min_length=1, max_length=120)
    date: dt.date | None = None
    payment_method: PaymentMethod | None = None
    notes: str | None = Field(default=None, max_length=500)


class PendingOut(BaseModel):
    id: str
    amount_paise: int
    source_app: SourceApp
    counterparty: str | None
    ref_last4: str | None
    detected_at: dt.datetime
    status: PendingStatus
    suggested_category: Category
    origin: Literal["detector", "simulator"]
    expense_id: str | None = None
    reviewed_at: dt.datetime | None = None
    created_at: dt.datetime


class SubmitResult(BaseModel):
    duplicate: bool
    transaction: PendingOut


class PendingList(BaseModel):
    items: list[PendingOut]
    counts: dict[str, int]


class PendingSummary(BaseModel):
    pending_count: int
    pending_total_paise: int


class AcceptResult(BaseModel):
    transaction: PendingOut
    expense_id: str
    replayed: bool = False
