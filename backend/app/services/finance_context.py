"""Loads everything the AI features need for one user, computed by the budget engine."""
from dataclasses import dataclass
from datetime import date, timedelta

from app.services import analytics_service as A
from app.services import budget_engine as engine
from app.services import routine_service
from app.utils import dates
from app.utils.periods import Period, period_containing


@dataclass
class FinanceContext:
    budget: dict
    period: Period
    today: date
    summary: engine.BudgetSummary
    expenses: list[engine.ExpenseItem]
    prev_period: Period
    prev_expenses: list[engine.ExpenseItem]
    categories: list[dict]

    @property
    def elapsed_days(self) -> int:
        """Days of the period so far, including today."""
        return max(1, min(self.period.total_days, (self.today - self.period.start).days + 1))

    def prev_same_point(self) -> list[engine.ExpenseItem]:
        """Previous-period expenses up to the same day number (fair 'so far' comparison)."""
        cutoff = self.prev_period.start + timedelta(days=self.elapsed_days - 1)
        return [e for e in self.prev_expenses if e.date <= cutoff]


async def load(db, user_id, offset: int = 0) -> FinanceContext:
    """offset=0: current period. offset=1: the previous (complete) period, etc."""
    budget = await A._require_budget(db, user_id)
    await routine_service.sync_current_period(db, user_id)  # due auto-deductions first
    real_today = dates.app_today()
    current = period_containing(real_today, budget["period_start_day"])
    periods = engine.previous_periods(current, offset + 2, budget["period_start_day"])
    period, prev = periods[-1 - offset], periods[-2 - offset]
    # For a finished period, evaluate it "as of" the day after it ended.
    today = real_today if offset == 0 else period.end + timedelta(days=1)

    expenses = await A._expenses(db, user_id, period.start, period.end)
    income = await A._income(db, user_id, period.start, period.end)
    if offset == 0:
        occurrences = await A._occurrences(db, user_id, period)
    else:
        docs = await db.planned_occurrences.find(
            {"user_id": user_id, "scheduled_date": A._date_range(period.start, period.end)},
            {"amount_paise": 1, "scheduled_date": 1, "status": 1}).to_list(None)
        occurrences = [engine.OccurrenceItem(d["amount_paise"], date.fromisoformat(d["scheduled_date"]), d["status"]) for d in docs]
    summary = engine.compute_summary(A._plan(budget), period, today, expenses, income, occurrences)
    prev_expenses = await A._expenses(db, user_id, prev.start, prev.end)
    return FinanceContext(budget, period, today, summary, expenses, prev, prev_expenses,
                          engine.category_breakdown(expenses))
