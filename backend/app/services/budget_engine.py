"""Deterministic budget engine. Pure functions: no database, no AI, no clock.

Every number PocketPilot shows about "how much can I spend" comes from here.

Inputs for one budget period:
  * the budget plan (allowance + additional income, savings target)
  * actual income records, actual expenses, planned occurrences
  * `today`

Formula
-------
  planned_income   = monthly_allowance + additional_income          (from the plan)
  extra_income     = income records NOT marked counts_as_planned    (bonus money)
  total_income     = planned_income + extra_income
      → logging "I received my allowance" with counts_as_planned=True does not add it twice.

  actual_expenses  = sum of all expenses dated in the period
      → an occurrence marked spent is counted ONLY through its linked expense.

  remaining_budget = total_income − actual_expenses

  reserved_upcoming = planned occurrences with status "planned" and
                      today ≤ scheduled_date ≤ period end
      → skipped occurrences reserve nothing; spent ones are already expenses;
        planned occurrences in the past ("overdue") reserve nothing and are
        reported separately so the user can mark them spent or skip them.

  free_to_spend    = remaining_budget − savings_target − reserved_upcoming
      → flexible money left for the rest of the period.

  Daily recommendation is fixed for the whole of today, so that spending
  during the day lowers "safe to spend today" instead of reshuffling it:
      pool_at_start_of_today = total_income − savings_target
                               − expenses before today
                               − planned expenses already spent today
                               − reserved_upcoming
      daily_recommendation  = max(0, pool_at_start_of_today) // days_remaining
      safe_to_spend_today   = max(0, daily_recommendation − unplanned spending today)

  projected_end_balance = remaining_budget − reserved_upcoming
      (what is left at period end if you only spend what's planned)
  savings_progress_pct  = clamp(projected_end_balance / savings_target, 0..100%)

  status:
      over_budget  remaining_budget < 0
      at_risk      free_to_spend < 0        (savings target or plans no longer covered)
      watch        spent share of (total_income − savings) runs >15 points ahead
                   of the share of the period already elapsed
      on_track     otherwise

All amounts are integer paise; division is floor division.
"""
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from app.utils.periods import Period, period_containing


@dataclass(frozen=True)
class Plan:
    monthly_allowance_paise: int
    additional_income_paise: int
    savings_target_paise: int


@dataclass(frozen=True)
class ExpenseItem:
    amount_paise: int
    date: date
    category: str = "other"
    planned: bool = False  # True if linked to a planned occurrence


@dataclass(frozen=True)
class IncomeItem:
    amount_paise: int
    date: date
    counts_as_planned: bool = False


@dataclass(frozen=True)
class OccurrenceItem:
    amount_paise: int
    scheduled_date: date
    status: str  # planned | spent | skipped


@dataclass(frozen=True)
class BudgetSummary:
    period_start: date
    period_end: date
    total_days: int
    days_remaining: int
    elapsed_pct: int
    planned_income_paise: int
    extra_income_paise: int
    received_planned_income_paise: int
    total_income_paise: int
    actual_expenses_paise: int
    planned_spent_paise: int
    unplanned_spent_paise: int
    remaining_budget_paise: int
    savings_target_paise: int
    reserved_upcoming_paise: int
    upcoming_count: int
    overdue_count: int
    free_to_spend_paise: int
    daily_recommendation_paise: int
    spent_today_unplanned_paise: int
    safe_to_spend_today_paise: int
    projected_end_balance_paise: int
    savings_progress_pct: int
    spent_pct: int
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


def _in(period: Period, d: date) -> bool:
    return period.start <= d <= period.end


def compute_summary(
    plan: Plan,
    period: Period,
    today: date,
    expenses: list[ExpenseItem],
    income: list[IncomeItem],
    occurrences: list[OccurrenceItem],
) -> BudgetSummary:
    expenses = [e for e in expenses if _in(period, e.date)]
    income = [i for i in income if _in(period, i.date)]
    occurrences = [o for o in occurrences if _in(period, o.scheduled_date)]

    planned_income = plan.monthly_allowance_paise + plan.additional_income_paise
    extra_income = sum(i.amount_paise for i in income if not i.counts_as_planned)
    received_planned = sum(i.amount_paise for i in income if i.counts_as_planned)
    total_income = planned_income + extra_income

    actual = sum(e.amount_paise for e in expenses)
    planned_spent = sum(e.amount_paise for e in expenses if e.planned)
    remaining = total_income - actual

    upcoming = [o for o in occurrences if o.status == "planned" and o.scheduled_date >= today]
    overdue = [o for o in occurrences if o.status == "planned" and o.scheduled_date < today]
    reserved = sum(o.amount_paise for o in upcoming)

    savings = plan.savings_target_paise
    free = remaining - savings - reserved

    days_remaining = period.days_remaining(today)
    before_today = sum(e.amount_paise for e in expenses if e.date < today)
    planned_today = sum(e.amount_paise for e in expenses if e.date == today and e.planned)
    unplanned_today = sum(e.amount_paise for e in expenses if e.date == today and not e.planned)
    pool = total_income - savings - before_today - planned_today - reserved
    daily = max(0, pool) // days_remaining if days_remaining else 0
    safe_today = max(0, daily - unplanned_today)

    projected_end = remaining - reserved
    if savings > 0:
        savings_pct = max(0, min(100, projected_end * 100 // savings))
    else:
        savings_pct = 100

    elapsed_days = period.total_days - days_remaining
    elapsed_pct = elapsed_days * 100 // period.total_days
    spendable = total_income - savings
    spent_pct = actual * 100 // spendable if spendable > 0 else (100 if actual else 0)

    if remaining < 0:
        status = "over_budget"
    elif free < 0:
        status = "at_risk"
    elif spent_pct > elapsed_pct + 15:
        status = "watch"
    else:
        status = "on_track"

    return BudgetSummary(
        period_start=period.start,
        period_end=period.end,
        total_days=period.total_days,
        days_remaining=days_remaining,
        elapsed_pct=elapsed_pct,
        planned_income_paise=planned_income,
        extra_income_paise=extra_income,
        received_planned_income_paise=received_planned,
        total_income_paise=total_income,
        actual_expenses_paise=actual,
        planned_spent_paise=planned_spent,
        unplanned_spent_paise=actual - planned_spent,
        remaining_budget_paise=remaining,
        savings_target_paise=savings,
        reserved_upcoming_paise=reserved,
        upcoming_count=len(upcoming),
        overdue_count=len(overdue),
        free_to_spend_paise=free,
        daily_recommendation_paise=daily,
        spent_today_unplanned_paise=unplanned_today,
        safe_to_spend_today_paise=safe_today,
        projected_end_balance_paise=projected_end,
        savings_progress_pct=savings_pct,
        spent_pct=spent_pct,
        status=status,
    )


def category_breakdown(expenses: list[ExpenseItem]) -> list[dict]:
    """Spending per category, largest first, with integer percentages."""
    totals: dict[str, int] = defaultdict(int)
    for e in expenses:
        totals[e.category] += e.amount_paise
    grand = sum(totals.values())
    rows = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        {"category": c, "amount_paise": a, "pct": (a * 100 // grand) if grand else 0}
        for c, a in rows
    ]


def daily_trend(expenses: list[ExpenseItem], period: Period, today: date, spendable_paise: int) -> list[dict]:
    """Per-day spending from period start to min(today, period end), with cumulative
    spend and the even-pace line (spendable spread evenly across the period)."""
    by_day: dict[date, int] = defaultdict(int)
    for e in expenses:
        if _in(period, e.date):
            by_day[e.date] += e.amount_paise
    rows, cumulative = [], 0
    last = min(today, period.end)
    d, i = period.start, 1
    while d <= last:
        cumulative += by_day.get(d, 0)
        rows.append({
            "date": d,
            "spent_paise": by_day.get(d, 0),
            "cumulative_paise": cumulative,
            "pace_paise": max(0, spendable_paise) * i // period.total_days,
        })
        d += timedelta(days=1)
        i += 1
    return rows


def previous_periods(period: Period, count: int, start_day: int) -> list[Period]:
    """`count` periods ending with `period`, oldest first."""
    periods = [period]
    while len(periods) < count:
        periods.insert(0, period_containing(periods[0].start - timedelta(days=1), start_day))
    return periods


def compare_categories(current: list[ExpenseItem], previous: list[ExpenseItem]) -> list[dict]:
    """Category totals for two periods with the change between them."""
    cur, prev = defaultdict(int), defaultdict(int)
    for e in current:
        cur[e.category] += e.amount_paise
    for e in previous:
        prev[e.category] += e.amount_paise
    rows = []
    for c in sorted(set(cur) | set(prev)):
        change_pct = ((cur[c] - prev[c]) * 100 // prev[c]) if prev[c] else None
        rows.append({
            "category": c,
            "current_paise": cur[c],
            "previous_paise": prev[c],
            "change_paise": cur[c] - prev[c],
            "change_pct": change_pct,
        })
    rows.sort(key=lambda r: -r["current_paise"])
    return rows
