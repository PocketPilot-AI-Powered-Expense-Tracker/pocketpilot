"""Recurring expenses: 'deduct automatically' vs 'deduct when I tap', and the Rent category."""
import asyncio

from app.utils.categorize import suggest_category

RENT = {"name": "Room rent", "amount_paise": 600000, "category": "rent", "frequency": "monthly",
        "day_of_month": 5, "start_date": "2026-11-01", "deduction_mode": "auto"}
TEA = {"name": "Tea", "amount_paise": 3000, "category": "food", "frequency": "daily", "start_date": "2026-11-10"}


def expenses(client, h):
    return client.get("/api/expenses", headers=h).json()


def safe(client, h):
    return client.get("/api/analytics/safe-to-spend", headers=h).json()


def test_rent_category_and_suggestion(client, budget_user):
    h = budget_user["headers"]
    res = client.post("/api/expenses", json={"amount_paise": 500000, "category": "rent", "description": "PG rent",
                                             "date": "2026-11-01"}, headers=h)
    assert res.status_code == 201
    assert suggest_category("Sunshine PG") == "rent" and suggest_category("Landlord Sharma") == "rent"
    assert suggest_category("Hostel Mess") == "food"


def test_default_mode_is_manual(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json=TEA, headers=h).json()
    assert r["deduction_mode"] == "manual"
    # Past tea dates are NOT deducted automatically; they wait for a tap
    assert expenses(client, h)["total"] == 0
    occ = client.get("/api/occurrences", headers=h).json()
    assert all(o["status"] == "planned" and o["deduction_mode"] == "manual" for o in occ)


def test_auto_deducts_due_dates_exactly_once(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json=RENT, headers=h)
    assert r.status_code == 201 and r.json()["deduction_mode"] == "auto"
    # Today is 15 Nov: the 5 Nov rent is due -> one expense, dated 5 Nov
    for _ in range(3):  # repeated loads never duplicate it
        data = expenses(client, h)
    assert data["total"] == 1
    exp = data["items"][0]
    assert (exp["amount_paise"], exp["category"], exp["date"], exp["auto_deducted"], exp["source"]) == \
        (600000, "rent", "2026-11-05", True, "routine")
    s = safe(client, h)
    assert s["actual_expenses_paise"] == 600000 and s["reserved_upcoming_paise"] == 0
    occ = client.get("/api/occurrences", headers=h).json()
    assert len(occ) == 1 and occ[0]["status"] == "spent" and occ[0]["auto_deducted"]


def test_future_auto_dates_are_reserved_not_deducted(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "day_of_month": 25}, headers=h)
    assert expenses(client, h)["total"] == 0
    assert safe(client, h)["reserved_upcoming_paise"] == 600000


def test_auto_catches_up_missed_months_within_lookback(client, budget_user):
    h = budget_user["headers"]
    # Started 1 Sep; today is 15 Nov. Catch-up covers the last 62 days (from 14 Sep),
    # so 5 Oct and 5 Nov are recorded, but 5 Sep (too old) is not back-filled.
    client.post("/api/routines", json={**RENT, "start_date": "2026-09-01"}, headers=h)
    dates = sorted(e["date"] for e in expenses(client, h)["items"])
    assert dates == ["2026-10-05", "2026-11-05"]


def test_deleting_auto_expense_skips_that_date(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json=RENT, headers=h)
    exp = expenses(client, h)["items"][0]
    assert client.delete(f"/api/expenses/{exp['id']}", headers=h).status_code == 204
    assert expenses(client, h)["total"] == 0  # not re-deducted
    occ = client.get("/api/occurrences", headers=h).json()[0]
    assert occ["status"] == "skipped"
    # Restoring it means "it did happen": it gets deducted again
    client.post(f"/api/occurrences/{occ['id']}/restore", headers=h)
    assert expenses(client, h)["total"] == 1


def test_switching_modes(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json={**RENT, "deduction_mode": "manual"}, headers=h).json()
    assert expenses(client, h)["total"] == 0
    client.put(f"/api/routines/{r['id']}", json={**RENT, "deduction_mode": "auto"}, headers=h)
    assert expenses(client, h)["total"] == 1
    client.put(f"/api/routines/{r['id']}", json={**RENT, "deduction_mode": "manual"}, headers=h)
    assert expenses(client, h)["total"] == 1  # already-recorded rent stays


def test_paused_auto_rule_does_not_deduct(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json={**RENT, "day_of_month": 20}, headers=h).json()
    client.post(f"/api/routines/{r['id']}/pause", headers=h)
    from app.utils import dates
    import datetime as dt

    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(dates, "app_today", lambda: dt.date(2026, 11, 25))
    try:
        assert expenses(client, h)["total"] == 0
    finally:
        mp.undo()


def test_auto_deduction_is_private(client, budget_user, other_user):
    client.post("/api/routines", json=RENT, headers=budget_user["headers"])
    expenses(client, budget_user["headers"])
    assert expenses(client, other_user["headers"])["total"] == 0


def test_dashboard_marks_modes(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "day_of_month": 18}, headers=h)
    client.post("/api/routines", json={**TEA, "start_date": "2026-11-15"}, headers=h)
    d = client.get("/api/analytics/dashboard", headers=h).json()
    modes = {o["name"]: o["deduction_mode"] for o in d["upcoming"]}
    assert modes == {"Room rent": "auto", "Tea": "manual"}


def test_first_dashboard_load_counts_auto_deduction(client, budget_user):
    """Regression: the dashboard must record due automatic deductions BEFORE calculating totals."""
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "amount_paise": 400000, "day_of_month": 1}, headers=h)
    d = client.get("/api/analytics/dashboard", headers=h).json()  # very first load after adding rent
    assert d["summary"]["actual_expenses_paise"] == 400000
    assert d["categories"] and d["categories"][0]["category"] == "rent"
    assert [t["description"] for t in d["recent_transactions"]] == ["Room rent"]


def test_first_load_of_other_views_counts_auto_deduction(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "day_of_month": 1}, headers=h)
    assert client.get("/api/analytics/safe-to-spend", headers=h).json()["actual_expenses_paise"] == 600000


def test_first_report_and_assistant_count_auto_deduction(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "day_of_month": 1}, headers=h)
    assert client.get("/api/ai/report", headers=h).json()["totals"]["expenses_paise"] == 600000


def test_first_category_and_comparison_count_auto_deduction(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**RENT, "day_of_month": 1}, headers=h)
    assert client.get("/api/analytics/categories", headers=h).json()["categories"][0]["amount_paise"] == 600000


# ---- "Deduct for this month too" when adding a monthly expense mid-month (today = 15 Nov) ----

NEW_RENT = {"name": "Flat rent", "amount_paise": 400000, "category": "rent", "frequency": "monthly",
            "day_of_month": 1, "deduction_mode": "auto"}  # start_date defaults to today (15 Nov)


def test_default_no_does_not_deduct_this_month(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json=NEW_RENT, headers=h)
    assert expenses(client, h)["total"] == 0
    assert safe(client, h)["actual_expenses_paise"] == 0


def test_yes_deducts_this_month_on_due_date_once(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json={**NEW_RENT, "deduct_this_month": True}, headers=h).json()
    assert r["this_month_expense_id"]
    for _ in range(2):
        items = expenses(client, h)["items"]
    assert [(e["date"], e["amount_paise"], e["category"], e["auto_deducted"]) for e in items] == \
        [("2026-11-01", 400000, "rent", True)]
    d = client.get("/api/analytics/dashboard", headers=h).json()
    assert d["summary"]["actual_expenses_paise"] == 400000
    occ = client.get("/api/occurrences", headers=h).json()
    assert [(o["original_date"], o["status"]) for o in occ] == [("2026-11-01", "spent")]


def test_yes_in_tap_mode_records_immediately(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**NEW_RENT, "deduction_mode": "manual", "deduct_this_month": True}, headers=h)
    exp = expenses(client, h)["items"][0]
    assert exp["date"] == "2026-11-01" and exp["auto_deducted"] is False
    # Deleting a tap-mode one puts the date back as "did this happen?" (planned, overdue)
    client.delete(f"/api/expenses/{exp['id']}", headers=h)
    occ = client.get("/api/occurrences", headers=h).json()[0]
    assert occ["status"] == "planned" and expenses(client, h)["total"] == 0


def test_deleting_this_month_auto_expense_skips_it(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={**NEW_RENT, "deduct_this_month": True}, headers=h)
    exp = expenses(client, h)["items"][0]
    client.delete(f"/api/expenses/{exp['id']}", headers=h)
    assert expenses(client, h)["total"] == 0  # not re-deducted


def test_deduct_this_month_rejected_when_not_applicable(client, budget_user):
    h = budget_user["headers"]
    weekly = {**NEW_RENT, "frequency": "weekly", "weekday": 0, "deduct_this_month": True}
    assert client.post("/api/routines", json=weekly, headers=h).status_code == 422
    not_passed = {**NEW_RENT, "day_of_month": 20, "deduct_this_month": True}
    assert client.post("/api/routines", json=not_passed, headers=h).status_code == 422
    due_today = {**NEW_RENT, "day_of_month": 15, "deduct_this_month": True}
    assert client.post("/api/routines", json=due_today, headers=h).status_code == 422
    covered = {**NEW_RENT, "start_date": "2026-11-01", "deduct_this_month": True}
    assert client.post("/api/routines", json=covered, headers=h).status_code == 422
    assert client.get("/api/routines", headers=h).json() == [] and expenses(client, h)["total"] == 0


def test_flag_ignored_on_update(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json=NEW_RENT, headers=h).json()
    res = client.put(f"/api/routines/{r['id']}", json={**NEW_RENT, "amount_paise": 450000, "deduct_this_month": True}, headers=h)
    assert res.status_code == 200 and expenses(client, h)["total"] == 0
