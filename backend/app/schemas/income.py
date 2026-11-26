import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import PositivePaise, check_not_future
from app.utils import dates


class IncomeIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount_paise: int = PositivePaise
    source: str = Field(min_length=1, max_length=60, description="e.g. Pocket money, Scholarship, Part-time job")
    date: dt.date
    description: str | None = Field(default=None, max_length=200)
    # True = this is the allowance/income already counted in the monthly budget plan,
    # so it must NOT be added on top again (prevents double counting).
    counts_as_planned: bool = False

    @field_validator("date")
    @classmethod
    def not_future(cls, v: dt.date) -> dt.date:
        return check_not_future(v, dates.app_today())

    @field_validator("description")
    @classmethod
    def empty_to_none(cls, v):
        return v or None


class IncomeOut(BaseModel):
    id: str
    amount_paise: int
    source: str
    date: dt.date
    description: str | None = None
    counts_as_planned: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class IncomeList(BaseModel):
    items: list[IncomeOut]
    total: int
    total_amount_paise: int
