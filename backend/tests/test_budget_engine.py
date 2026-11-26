"""Pure budget-engine tests: no database, no HTTP."""
from datetime import date

from app.services.budget_engine import (ExpenseItem as E, IncomeItem as I, OccurrenceItem as O, Plan,
                                        category_breakdown, compare_categories, compute_summary, daily_trend)
from app.services.routine_service import rule_dates
from app.utils.periods import Period

NOV = Period(date(2026, 11, 1), date(2026, 11, 30))
TODAY = date(2026, 11, 16)  # 15 days remaining including today
PLAN = Plan(800000, 0, 0)


def summary(plan=PLAN, expenses=(), income=(), occ=(), today=TODAY):
    return compute_summary(plan, NOV, today, list(expenses), list(income), list(occ))


def test_spec_example():
    # Budget ₹8,000, spent ₹2,000, ₹1,000 planned ahead, 15 days left.
    s = summary(expenses=[E(200000, date(2026, 11, 5))], occ=[O(100000, date(2026, 11, 20), "planned")])
    assert s.days_remaining == 15
    assert s.remaining_budget_paise == 600000
    assert s.reserved_upcoming_paise == 100000
    assert s.free_to_spend_paise == 500000
    assert s.daily_recommendation_paise == 500000 // 15  # ₹333.33
    assert s.safe_to_spend_today_paise == 33333
    assert s.status == "on_track"


def test_savings_target_is_protected():
    s = summary(plan=Plan(800000, 50000, 150000))
    assert s.total_income_paise == 850000
    assert s.free_to_spend_paise == 700000


def test_allowance_logged_as_planned_income_is_not_double_counted():
    s = summary(income=[I(800000, date(2026, 11, 1), counts_as_planned=True)])
    assert s.total_income_paise == 800000
    assert s.received_planned_income_paise == 800000


def test_extra_income_is_added():
    s = summary(income=[I(200000, date(2026, 11, 3))])
    assert s.total_income_paise == 1000000
    assert s.extra_income_paise == 200000


def test_skipped_and_spent_occurrences_reserve_nothing():
    s = summary(occ=[O(30000, date(2026, 11, 20), "skipped"), O(30000, date(2026, 11, 21), "spent")])
    assert s.reserved_upcoming_paise == 0


def test_spent_occurrence_counted_once_via_its_expense():
    s = summary(expenses=[E(30000, date(2026, 11, 10), planned=True)], occ=[O(30000, date(2026, 11, 10), "spent")])
    assert s.actual_expenses_paise == 30000
    assert s.reserved_upcoming_paise == 0
    assert s.remaining_budget_paise == 770000


def test_overdue_planned_not_reserved_but_reported():
    s = summary(occ=[O(30000, date(2026, 11, 10), "planned")])
    assert s.reserved_upcoming_paise == 0
    assert s.overdue_count == 1


def test_occurrence_today_is_reserved():
    s = summary(occ=[O(30000, TODAY, "planned")])
    assert s.reserved_upcoming_paise == 30000 and s.upcoming_count == 1


def test_unplanned_spending_today_reduces_safe_to_spend_but_not_daily():
    before = summary()
    after = summary(expenses=[E(10000, TODAY)])
    assert after.daily_recommendation_paise == before.daily_recommendation_paise
    assert after.safe_to_spend_today_paise == before.safe_to_spend_today_paise - 10000
    huge = summary(expenses=[E(500000, TODAY)])
    assert huge.safe_to_spend_today_paise == 0


def test_marking_todays_plan_spent_does_not_change_daily_allowance():
    planned = summary(occ=[O(30000, TODAY, "planned")])
    spent = summary(expenses=[E(30000, TODAY, planned=True)], occ=[O(30000, TODAY, "spent")])
    assert planned.daily_recommendation_paise == spent.daily_recommendation_paise
    assert planned.safe_to_spend_today_paise == spent.safe_to_spend_today_paise
    assert planned.free_to_spend_paise == spent.free_to_spend_paise


def test_records_outside_period_ignored():
    s = summary(expenses=[E(100000, date(2026, 10, 31))], income=[I(100000, date(2026, 12, 1))])
    assert s.actual_expenses_paise == 0 and s.total_income_paise == 800000


def test_statuses():
    assert summary(expenses=[E(900000, date(2026, 11, 2))]).status == "over_budget"
    assert summary(plan=Plan(800000, 0, 300000), expenses=[E(600000, date(2026, 11, 2))]).status == "at_risk"
    # Half the period elapsed but ~88% spent -> watch
    assert summary(expenses=[E(700000, date(2026, 11, 2))]).status == "watch"
    assert summary(expenses=[E(300000, date(2026, 11, 2))]).status == "on_track"


def test_no_negative_daily_when_overspent():
    s = summary(expenses=[E(900000, date(2026, 11, 2))])
    assert s.daily_recommendation_paise == 0 and s.safe_to_spend_today_paise == 0


def test_savings_progress():
    s = summary(plan=Plan(800000, 0, 200000), expenses=[E(700000, date(2026, 11, 2))])
    assert s.projected_end_balance_paise == 100000
    assert s.savings_progress_pct == 50


def test_category_breakdown_and_comparison():
    exp = [E(30000, TODAY, "food"), E(10000, TODAY, "food"), E(20000, TODAY, "transportation")]
    rows = category_breakdown(exp)
    assert rows[0] == {"category": "food", "amount_paise": 40000, "pct": 66}
    cmp = compare_categories(exp, [E(20000, date(2026, 10, 5), "food")])
    food = next(r for r in cmp if r["category"] == "food")
    assert food["change_paise"] == 20000 and food["change_pct"] == 100
    transport = next(r for r in cmp if r["category"] == "transportation")
    assert transport["change_pct"] is None


def test_daily_trend_cumulative_and_pace():
    rows = daily_trend([E(1000, date(2026, 11, 1)), E(500, date(2026, 11, 3))], NOV, date(2026, 11, 3), 300000)
    assert [r["cumulative_paise"] for r in rows] == [1000, 1000, 1500]
    assert rows[-1]["pace_paise"] == 300000 * 3 // 30


def test_rule_dates_daily_weekly_monthly():
    base = {"start_date": "2026-11-01", "end_date": None}
    assert len(rule_dates({**base, "frequency": "daily"}, date(2026, 11, 1), date(2026, 11, 30))) == 30
    sundays = rule_dates({**base, "frequency": "weekly", "weekday": 6}, date(2026, 11, 1), date(2026, 11, 30))
    assert all(d.weekday() == 6 for d in sundays) and len(sundays) == 5
    monthly = rule_dates({**base, "frequency": "monthly", "day_of_month": 10}, date(2026, 11, 1), date(2026, 12, 31))
    assert monthly == [date(2026, 11, 10), date(2026, 12, 10)]


def test_rule_dates_respect_start_and_end():
    rule = {"frequency": "daily", "start_date": "2026-11-10", "end_date": "2026-11-12"}
    assert rule_dates(rule, date(2026, 11, 1), date(2026, 11, 30)) == [date(2026, 11, 10), date(2026, 11, 11), date(2026, 11, 12)]
