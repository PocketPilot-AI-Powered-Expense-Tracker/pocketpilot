"""Expense and income CRUD, filters, validation and user isolation."""
import pytest

EXP = {"amount_paise": 15000, "category": "food", "description": "Lunch at canteen",
       "date": "2026-11-15", "payment_method": "upi"}
INC = {"amount_paise": 200000, "source": "Part-time job", "date": "2026-11-10"}


def test_expense_crud(client, budget_user):
    h = budget_user["headers"]
    res = client.post("/api/expenses", json=EXP, headers=h)
    assert res.status_code == 201, res.text
    exp = res.json()
    assert exp["source"] == "manual" and exp["occurrence_id"] is None

    assert client.get(f"/api/expenses/{exp['id']}", headers=h).json()["description"] == "Lunch at canteen"
    upd = client.put(f"/api/expenses/{exp['id']}", json={**EXP, "amount_paise": 18000, "notes": "with juice"}, headers=h)
    assert upd.status_code == 200 and upd.json()["amount_paise"] == 18000

    assert client.delete(f"/api/expenses/{exp['id']}", headers=h).status_code == 204
    assert client.get(f"/api/expenses/{exp['id']}", headers=h).status_code == 404


def test_expense_list_filters_and_search(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/expenses", json=EXP, headers=h)
    client.post("/api/expenses", json={**EXP, "category": "transportation", "description": "Auto to college",
                                       "date": "2026-11-02", "amount_paise": 5000}, headers=h)
    client.post("/api/expenses", json={**EXP, "description": "Dinner", "date": "2026-10-20"}, headers=h)

    all_ = client.get("/api/expenses", headers=h).json()
    assert all_["total"] == 3
    assert [e["date"] for e in all_["items"]] == ["2026-11-15", "2026-11-02", "2026-10-20"]  # newest first

    nov = client.get("/api/expenses", params={"from": "2026-11-01", "to": "2026-11-30"}, headers=h).json()
    assert nov["total"] == 2 and nov["total_amount_paise"] == 20000
    food = client.get("/api/expenses", params={"category": "food"}, headers=h).json()
    assert food["total"] == 2
    search = client.get("/api/expenses", params={"q": "COLLEGE"}, headers=h).json()
    assert [e["description"] for e in search["items"]] == ["Auto to college"]
    # Regex characters are treated literally
    assert client.get("/api/expenses", params={"q": ".*"}, headers=h).json()["total"] == 0


@pytest.mark.parametrize("patch", [
    {"amount_paise": 0},
    {"amount_paise": 12.5},
    {"category": "groceries"},
    {"description": ""},
    {"date": "2026-11-16"},  # tomorrow
    {"payment_method": "bitcoin"},
])
def test_expense_validation(client, budget_user, patch):
    assert client.post("/api/expenses", json={**EXP, **patch}, headers=budget_user["headers"]).status_code == 422


def test_income_crud_and_filters(client, budget_user):
    h = budget_user["headers"]
    res = client.post("/api/income", json=INC, headers=h)
    assert res.status_code == 201
    inc = res.json()
    assert inc["counts_as_planned"] is False
    upd = client.put(f"/api/income/{inc['id']}", json={**INC, "source": "Freelance", "description": "Logo design"}, headers=h)
    assert upd.json()["source"] == "Freelance"
    assert client.get("/api/income", params={"q": "logo"}, headers=h).json()["total"] == 1
    assert client.delete(f"/api/income/{inc['id']}", headers=h).status_code == 204
    assert client.get("/api/income", headers=h).json()["total"] == 0


def test_income_validation(client, budget_user):
    h = budget_user["headers"]
    assert client.post("/api/income", json={**INC, "amount_paise": -5}, headers=h).status_code == 422
    assert client.post("/api/income", json={**INC, "source": ""}, headers=h).status_code == 422


def test_users_cannot_touch_each_others_transactions(client, budget_user, other_user):
    exp = client.post("/api/expenses", json=EXP, headers=budget_user["headers"]).json()
    inc = client.post("/api/income", json=INC, headers=budget_user["headers"]).json()
    oh = other_user["headers"]

    assert client.get("/api/expenses", headers=oh).json()["total"] == 0
    assert client.get("/api/income", headers=oh).json()["total"] == 0
    assert client.get(f"/api/expenses/{exp['id']}", headers=oh).status_code == 404
    assert client.put(f"/api/expenses/{exp['id']}", json=EXP, headers=oh).status_code == 404
    assert client.delete(f"/api/expenses/{exp['id']}", headers=oh).status_code == 404
    assert client.delete(f"/api/income/{inc['id']}", headers=oh).status_code == 404
    # Still intact for the owner
    assert client.get(f"/api/expenses/{exp['id']}", headers=budget_user["headers"]).status_code == 200


def test_invalid_id_is_404(client, budget_user):
    assert client.get("/api/expenses/not-an-id", headers=budget_user["headers"]).status_code == 404


def test_transactions_require_auth(client):
    assert client.get("/api/expenses").status_code == 401
    assert client.post("/api/income", json=INC).status_code == 401
