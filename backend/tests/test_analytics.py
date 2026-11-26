"""Dashboard/analytics endpoints wire real data through the engine correctly."""


def test_dashboard_combines_everything_without_double_counting(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/expenses", json={"amount_paise": 50000, "category": "shopping", "description": "T-shirt",
                                       "date": "2026-11-05"}, headers=h)
    client.post("/api/income", json={"amount_paise": 800000, "source": "Pocket money", "date": "2026-11-01",
                                     "counts_as_planned": True}, headers=h)
    client.post("/api/income", json={"amount_paise": 100000, "source": "Gift", "date": "2026-11-08"}, headers=h)
    client.post("/api/routines", json={"name": "Movie", "amount_paise": 30000, "category": "entertainment",
                                       "frequency": "monthly", "day_of_month": 20}, headers=h)

    res = client.get("/api/analytics/dashboard", headers=h)
    assert res.status_code == 200, res.text
    d = res.json()
    s = d["summary"]
    assert s["total_income_paise"] == 850000 + 100000  # plan + gift; allowance not counted twice
    assert s["actual_expenses_paise"] == 50000
    assert s["reserved_upcoming_paise"] == 30000
    assert s["free_to_spend_paise"] == 950000 - 50000 - 150000 - 30000
    assert s["days_remaining"] == 16
    assert d["categories"][0]["category"] == "shopping"
    assert len(d["daily_trend"]) == 15  # 1..15 Nov
    # Only Nov has activity, so empty earlier months are dropped from the trend
    assert [t["label"] for t in d["monthly_trend"]] == ["Nov 2026"]
    assert d["upcoming"][0]["name"] == "Movie"
    assert {r["type"] for r in d["recent_transactions"]} == {"expense", "income"}


def test_editing_and_deleting_expense_recalculates(client, budget_user):
    h = budget_user["headers"]
    exp = client.post("/api/expenses", json={"amount_paise": 50000, "category": "food", "description": "Pizza",
                                             "date": "2026-11-15"}, headers=h).json()
    base = client.get("/api/analytics/safe-to-spend", headers=h).json()
    client.put(f"/api/expenses/{exp['id']}", json={"amount_paise": 20000, "category": "food", "description": "Pizza",
                                                   "date": "2026-11-15"}, headers=h)
    edited = client.get("/api/analytics/safe-to-spend", headers=h).json()
    assert edited["remaining_budget_paise"] == base["remaining_budget_paise"] + 30000
    client.delete(f"/api/expenses/{exp['id']}", headers=h)
    assert client.get("/api/analytics/safe-to-spend", headers=h).json()["actual_expenses_paise"] == 0


def test_budget_change_recalculates(client, budget_user):
    h = budget_user["headers"]
    client.put("/api/budget", json={"monthly_allowance_paise": 1000000, "additional_income_paise": 0,
                                    "savings_target_paise": 0, "period_start_day": 1}, headers=h)
    assert client.get("/api/analytics/safe-to-spend", headers=h).json()["total_income_paise"] == 1000000


def test_monthly_comparison_and_categories(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/expenses", json={"amount_paise": 20000, "category": "food", "description": "a",
                                       "date": "2026-10-10"}, headers=h)
    client.post("/api/expenses", json={"amount_paise": 30000, "category": "food", "description": "b",
                                       "date": "2026-11-10"}, headers=h)
    cmp = client.get("/api/analytics/monthly-comparison", headers=h).json()
    assert [t["label"] for t in cmp["trend"]] == ["Oct 2026", "Nov 2026"]
    assert cmp["previous_total_paise"] == 20000 and cmp["current_total_paise"] == 30000
    assert cmp["categories"][0]["change_pct"] == 50
    prev = client.get("/api/analytics/categories", params={"offset": 1}, headers=h).json()
    assert prev["period_start"] == "2026-10-01" and prev["categories"][0]["amount_paise"] == 20000


def test_analytics_requires_budget(client, user):
    assert client.get("/api/analytics/dashboard", headers=user["headers"]).status_code == 404
