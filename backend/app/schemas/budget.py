from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.utils.money import MAX_AMOUNT_PAISE

Paise = Field(ge=0, le=MAX_AMOUNT_PAISE, description="Amount in integer paise (₹1 = 100)")


class BudgetIn(BaseModel):
    monthly_allowance_paise: int = Paise
    additional_income_paise: int = Field(default=0, ge=0, le=MAX_AMOUNT_PAISE)
    savings_target_paise: int = Field(default=0, ge=0, le=MAX_AMOUNT_PAISE)
    period_start_day: int = Field(default=1, ge=1, le=28, description="Day of month the budget period starts")
    # Money already spent this budget month before today (e.g. joined mid-month).
    # None = leave unchanged, 0 = remove it. Stored as one expense, not on the budget.
    spent_before_today_paise: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_PAISE)

    @model_validator(mode="after")
    def savings_within_income(self):
        if self.savings_target_paise > self.monthly_allowance_paise + self.additional_income_paise:
            raise ValueError("Savings target cannot be more than your planned monthly income")
        return self


class PeriodOut(BaseModel):
    start: date
    end: date
    total_days: int
    days_remaining: int


class BudgetOut(BudgetIn):
    id: str
    spent_before_today_paise: int = 0
    planned_income_paise: int
    planned_spendable_paise: int
    current_period: PeriodOut
    created_at: datetime
    updated_at: datetime
