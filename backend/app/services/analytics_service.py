"""Loads a user's data from MongoDB and feeds it to the pure budget engine."""
from datetime import date, timedelta

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING

from app.services import budget_engine as engine
from app.services import routine_service
from app.services.budget_service import get_budget_doc
from app.utils import dates
from app.utils.periods import Period, period_containing
from app.utils.serialize import date_str, to_out


async def _require_budget(db, user_id) -> dict:
    budget = await get_budget_doc(db, user_id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Set up your budget first")
    return budget


def _plan(budget: dict) -> engine.Plan:
    return engine.Plan(budget["monthly_allowance_paise"], budget["additional_income_paise"],
                       budget["savings_target_paise"])


def _date_range(start: date, end: date) -> dict:
    return {"$gte": date_str(start), "$lte": date_str(end)}


async def _expenses(db, user_id, start: date, end: date) -> list[engine.ExpenseItem]:
    docs = await db.expenses.find({"user_id": user_id, "date": _date_range(start, end)},
                                  {"amount_paise": 1, "date": 1, "category": 1, "occurrence_id": 1}).to_list(None)
    return [engine.ExpenseItem(d["amount_paise"], date.fromisoformat(d["date"]), d["category"],
                               planned=bool(d.get("occurrence_id"))) for d in docs]


async def _income(db, user_id, start: date, end: date) -> list[engine.IncomeItem]:
    docs = await db.income.find({"user_id": user_id, "date": _date_range(start, end)},
                                {"amount_paise": 1, "date": 1, "counts_as_planned": 1}).to_list(None)
    return [engine.IncomeItem(d["amount_paise"], date.fromisoformat(d["date"]), d.get("counts_as_planned", False))
            for d in docs]


async def _occurrences(db, user_id, period: Period) -> list[engine.OccurrenceItem]:
    await routine_service.ensure_occurrences(db, user_id, period.start, period.end, earliest=period.start)
    docs = await db.planned_occurrences.find({"user_id": user_id, "scheduled_date": _date_range(period.start, period.end)},
                                             {"amount_paise": 1, "scheduled_date": 1, "status": 1}).to_list(None)
    return [engine.OccurrenceItem(d["amount_paise"], date.fromisoformat(d["scheduled_date"]), d["status"]) for d in docs]


async def summary_for_current_period(db, user_id):
    budget = await _require_budget(db, user_id)
    # Record any automatic deductions that are due BEFORE reading expenses,
    # otherwise a just-deducted rent would be missing from the totals.
    await routine_service.sync_current_period(db, user_id)
    today = dates.app_today()
    period = period_containing(today, budget["period_start_day"])
    expenses = await _expenses(db, user_id, period.start, period.end)
    income = await _income(db, user_id, period.start, period.end)
    occurrences = await _occurrences(db, user_id, period)
    summary = engine.compute_summary(_plan(budget), period, today, expenses, income, occurrences)
    return budget, period, today, expenses, summary


async def safe_to_spend(db, user_id) -> dict:
    *_, summary = await summary_for_current_period(db, user_id)
    return summary.to_dict()


async def category_breakdown(db, user_id, offset: int = 0) -> dict:
    """offset=0 is the current period, 1 the previous one, etc."""
    budget = await _require_budget(db, user_id)
    await routine_service.sync_current_period(db, user_id)
    periods = engine.previous_periods(period_containing(dates.app_today(), budget["period_start_day"]),
                                      offset + 1, budget["period_start_day"])
    p = periods[0]
    exp = await _expenses(db, user_id, p.start, p.end)
    return {"period_start": p.start, "period_end": p.end, "categories": engine.category_breakdown(exp)}


async def monthly_comparison(db, user_id, months: int = 6) -> dict:
    budget = await _require_budget(db, user_id)
    await routine_service.sync_current_period(db, user_id)
    current = period_containing(dates.app_today(), budget["period_start_day"])
    periods = engine.previous_periods(current, months, budget["period_start_day"])
    exp = await _expenses(db, user_id, periods[0].start, current.end)
    inc = await _income(db, user_id, periods[0].start, current.end)
    plan = _plan(budget)
    trend = []
    for p in periods:
        p_exp = [e for e in exp if p.start <= e.date <= p.end]
        p_extra = sum(i.amount_paise for i in inc if p.start <= i.date <= p.end and not i.counts_as_planned)
        trend.append({
            "period_start": p.start,
            "period_end": p.end,
            "label": p.start.strftime("%b %Y") if p.start.day == 1 else f"{p.start:%d %b}",
            # Uses the *current* plan for past periods (budget history isn't stored yet).
            "income_paise": plan.monthly_allowance_paise + plan.additional_income_paise + p_extra,
            "expenses_paise": sum(e.amount_paise for e in p_exp),
        })
    # Drop leading months with no activity (e.g. before the user joined),
    # so the chart doesn't show "income" for months that were never tracked.
    while len(trend) > 1 and trend[0]["expenses_paise"] == 0 and \
            trend[0]["income_paise"] == plan.monthly_allowance_paise + plan.additional_income_paise:
        trend.pop(0)
    prev = periods[-2] if len(periods) > 1 else None
    cur_exp = [e for e in exp if current.start <= e.date <= current.end]
    prev_exp = [e for e in exp if prev and prev.start <= e.date <= prev.end]
    return {
        "trend": trend,
        "categories": engine.compare_categories(cur_exp, prev_exp),
        "current_total_paise": sum(e.amount_paise for e in cur_exp),
        "previous_total_paise": sum(e.amount_paise for e in prev_exp),
    }


async def dashboard(db, user_id) -> dict:
    budget, period, today, expenses, summary = await summary_for_current_period(db, user_id)
    spendable = summary.total_income_paise - summary.savings_target_paise

    upcoming = await db.planned_occurrences.find(
        {"user_id": user_id, "status": "planned",
         "scheduled_date": _date_range(today, min(period.end, today + timedelta(days=6)))}
    ).sort([("scheduled_date", ASCENDING), ("name", ASCENDING)]).limit(8).to_list(None)
    overdue = await db.planned_occurrences.find(
        {"user_id": user_id, "status": "planned", "scheduled_date": _date_range(period.start, today - timedelta(days=1))}
    ).sort("scheduled_date", ASCENDING).limit(8).to_list(None)

    recent_exp = await db.expenses.find({"user_id": user_id}).sort(
        [("date", DESCENDING), ("created_at", DESCENDING)]).limit(6).to_list(None)
    recent_inc = await db.income.find({"user_id": user_id}).sort(
        [("date", DESCENDING), ("created_at", DESCENDING)]).limit(6).to_list(None)
    recent = [{"type": "expense", **to_out(d)} for d in recent_exp] + [{"type": "income", **to_out(d)} for d in recent_inc]
    recent.sort(key=lambda r: (r["date"], r["created_at"]), reverse=True)

    comparison = await monthly_comparison(db, user_id, months=6)
    modes = await routine_service.deduction_modes(db, user_id)
    pending = await db.pending_transactions.find({"user_id": user_id, "status": "pending_review"},
                                                 {"amount_paise": 1}).to_list(None)
    return {
        "summary": summary.to_dict(),
        "categories": engine.category_breakdown(expenses),
        "daily_trend": engine.daily_trend(expenses, period, today, spendable),
        "monthly_trend": comparison["trend"],
        "upcoming": [{**to_out(d), "deduction_mode": modes.get(d["rule_id"], "manual")} for d in upcoming],
        "overdue": [{**to_out(d), "deduction_mode": modes.get(d["rule_id"], "manual")} for d in overdue],
        "recent_transactions": recent[:6],
        # Shown as a reminder only: pending transactions are NOT part of any total above.
        "pending_review": {"count": len(pending), "total_paise": sum(p["amount_paise"] for p in pending)},
    }
