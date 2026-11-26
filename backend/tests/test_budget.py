from datetime import date

import pytest

from app.utils.money import format_inr
from app.utils.periods import period_containing
from tests.conftest import auth_headers, register

BUDGET = {
    "monthly_allowance_paise": 800000,  # ₹8,000
    "additional_income_paise": 50000,  # ₹500
    "savings_target_paise": 150000,  # ₹1,500
    "period_start_day": 1,
}


def test_create_and_get_budget(client, user):
    res = client.post("/api/budget", json=BUDGET, headers=user["headers"])
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["planned_income_paise"] == 850000
    assert body["planned_spendable_paise"] == 700000
    assert client.get("/api/budget", headers=user["headers"]).json()["id"] == body["id"]
    assert client.get("/api/auth/me", headers=user["headers"]).json()["has_budget"] is True


def test_get_budget_before_setup_is_404(client, user):
    assert client.get("/api/budget", headers=user["headers"]).status_code == 404


def test_cannot_create_two_budgets(client, user):
    client.post("/api/budget", json=BUDGET, headers=user["headers"])
    assert client.post("/api/budget", json=BUDGET, headers=user["headers"]).status_code == 409


def test_update_budget(client, user):
    client.post("/api/budget", json=BUDGET, headers=user["headers"])
    res = client.put("/api/budget", json={**BUDGET, "savings_target_paise": 200000}, headers=user["headers"])
    assert res.status_code == 200
    assert res.json()["planned_spendable_paise"] == 650000


def test_update_without_budget_is_404(client, user):
    assert client.put("/api/budget", json=BUDGET, headers=user["headers"]).status_code == 404


@pytest.mark.parametrize(
    "patch",
    [
        {"monthly_allowance_paise": -1},
        {"period_start_day": 31},
        {"savings_target_paise": 900000},  # more than income
        {"monthly_allowance_paise": 12.5},  # paise must be integers
    ],
)
def test_invalid_budget_rejected(client, user, patch):
    res = client.post("/api/budget", json={**BUDGET, **patch}, headers=user["headers"])
    assert res.status_code == 422


def test_users_cannot_see_each_others_budget(client, user):
    client.post("/api/budget", json=BUDGET, headers=user["headers"])
    other = register(client, email="ravi@example.com", name="Ravi")
    other_headers = auth_headers(other["access_token"])
    assert client.get("/api/budget", headers=other_headers).status_code == 404
    # Ravi creating his own budget must not touch Asha's.
    client.post("/api/budget", json={**BUDGET, "monthly_allowance_paise": 100000, "savings_target_paise": 0},
                headers=other_headers)
    assert client.get("/api/budget", headers=user["headers"]).json()["monthly_allowance_paise"] == 800000


def test_period_calendar_month():
    p = period_containing(date(2026, 2, 14), 1)
    assert (p.start, p.end, p.total_days) == (date(2026, 2, 1), date(2026, 2, 28), 28)
    assert p.days_remaining(date(2026, 2, 14)) == 15  # includes today


def test_period_custom_start_day_crosses_year():
    p = period_containing(date(2026, 1, 3), 5)
    assert (p.start, p.end) == (date(2025, 12, 5), date(2026, 1, 4))
    assert p.days_remaining(date(2026, 1, 4)) == 1
    assert p.days_remaining(date(2026, 1, 5)) == 0


def test_format_inr_indian_grouping():
    assert format_inr(800000) == "₹8,000"
    assert format_inr(123456789) == "₹12,34,567.89"
    assert format_inr(-15050) == "-₹150.50"


# --- "Already spent this month" (joined mid-month) -----------------------------------
# Tests run with today = 2026-11-15 (see conftest), so the 1 Nov budget month has started.

def _opening(client, user):
    items = client.get("/api/expenses", headers=user["headers"]).json()["items"]
    return [e for e in items if e["source"] == "opening"]


def test_spent_before_today_creates_one_expense_dated_yesterday(client, user):
    res = client.post("/api/budget", json={**BUDGET, "spent_before_today_paise": 300000}, headers=user["headers"])
    assert res.status_code == 201, res.text
    assert res.json()["spent_before_today_paise"] == 300000
    [e] = _opening(client, user)
    assert e["amount_paise"] == 300000 and e["date"] == "2026-11-14"
    dash = client.get("/api/analytics/dashboard", headers=user["headers"]).json()
    assert dash["summary"]["actual_expenses_paise"] == 300000
    assert dash["summary"]["spent_today_unplanned_paise"] == 0  # doesn't eat today's safe-to-spend


def test_updating_spent_before_today_replaces_not_duplicates(client, user):
    client.post("/api/budget", json={**BUDGET, "spent_before_today_paise": 300000}, headers=user["headers"])
    res = client.put("/api/budget", json={**BUDGET, "spent_before_today_paise": 250000}, headers=user["headers"])
    assert res.json()["spent_before_today_paise"] == 250000
    assert [e["amount_paise"] for e in _opening(client, user)] == [250000]
    # omitted = unchanged
    client.put("/api/budget", json=BUDGET, headers=user["headers"])
    assert client.get("/api/budget", headers=user["headers"]).json()["spent_before_today_paise"] == 250000
    # 0 = removed
    client.put("/api/budget", json={**BUDGET, "spent_before_today_paise": 0}, headers=user["headers"])
    assert _opening(client, user) == []


def test_spent_before_today_rejected_when_month_starts_today(client, user):
    res = client.post("/api/budget", json={**BUDGET, "period_start_day": 15, "spent_before_today_paise": 1000},
                      headers=user["headers"])
    assert res.status_code == 422
    assert client.get("/api/budget", headers=user["headers"]).status_code == 404  # nothing half-saved
