"""Recurring rules, planned occurrences and how they interact with the budget."""
import asyncio

TEA = {"name": "Tea", "amount_paise": 3000, "category": "food", "frequency": "daily"}


def safe(client, h):
    return client.get("/api/analytics/safe-to-spend", headers=h).json()


def occurrences(client, h, **params):
    return client.get("/api/occurrences", params=params, headers=h).json()


def make_tea(client, h, **extra):
    res = client.post("/api/routines", json={**TEA, **extra}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def test_routine_generates_occurrences_from_start_date(client, budget_user):
    h = budget_user["headers"]
    rule = make_tea(client, h)
    assert rule["start_date"] == "2026-11-15" and rule["active"]
    occ = occurrences(client, h)
    # 15..30 Nov = 16 daily occurrences, none before the start date
    assert len(occ) == 16
    assert occ[0]["scheduled_date"] == "2026-11-15" and all(o["status"] == "planned" for o in occ)
    # Listing again does not create duplicates
    assert len(occurrences(client, h)) == 16


def test_planned_occurrences_reserve_but_are_not_expenses(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    s = safe(client, h)
    assert s["actual_expenses_paise"] == 0
    assert s["reserved_upcoming_paise"] == 16 * 3000
    assert client.get("/api/expenses", headers=h).json()["total"] == 0


def test_weekly_and_monthly_validation(client, budget_user):
    h = budget_user["headers"]
    assert client.post("/api/routines", json={**TEA, "frequency": "weekly"}, headers=h).status_code == 422
    assert client.post("/api/routines", json={**TEA, "frequency": "monthly", "day_of_month": 31}, headers=h).status_code == 422
    sunday = client.post("/api/routines", json={**TEA, "name": "Outside food", "amount_paise": 20000,
                                               "frequency": "weekly", "weekday": 6}, headers=h).json()
    dates = [o["scheduled_date"] for o in occurrences(client, h) if o["rule_id"] == sunday["id"]]
    assert dates == ["2026-11-15", "2026-11-22", "2026-11-29"]


def test_skip_releases_reserved_and_restore_brings_it_back(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[1]
    before = safe(client, h)["reserved_upcoming_paise"]
    res = client.post(f"/api/occurrences/{occ['id']}/skip", headers=h)
    assert res.status_code == 200 and res.json()["status"] == "skipped"
    assert safe(client, h)["reserved_upcoming_paise"] == before - 3000
    # Skipped occurrence is not re-generated
    assert len(occurrences(client, h)) == 16
    assert client.post(f"/api/occurrences/{occ['id']}/skip", headers=h).status_code == 409
    assert client.post(f"/api/occurrences/{occ['id']}/restore", headers=h).json()["status"] == "planned"
    assert safe(client, h)["reserved_upcoming_paise"] == before


def test_reschedule_updates_same_occurrence(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[0]
    res = client.post(f"/api/occurrences/{occ['id']}/reschedule", json={"new_date": "2026-11-20"}, headers=h)
    assert res.status_code == 200
    moved = res.json()
    assert moved["id"] == occ["id"] and moved["scheduled_date"] == "2026-11-20"
    assert moved["original_date"] == "2026-11-15" and moved["rescheduled"]
    # No new occurrence is generated for the original date
    all_occ = occurrences(client, h)
    assert len(all_occ) == 16
    assert sum(o["scheduled_date"] == "2026-11-20" for o in all_occ) == 2
    assert client.post(f"/api/occurrences/{occ['id']}/reschedule", json={"new_date": "2026-11-01"},
                       headers=h).status_code == 422


def test_mark_spent_creates_exactly_one_expense(client, budget_user, db):
    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[0]
    reserved_before = safe(client, h)["reserved_upcoming_paise"]

    res = client.post(f"/api/occurrences/{occ['id']}/spend", json={"amount_paise": 3500}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["occurrence"]["status"] == "spent"

    exp = client.get(f"/api/expenses/{body['expense_id']}", headers=h).json()
    assert exp["amount_paise"] == 3500 and exp["source"] == "routine" and exp["occurrence_id"] == occ["id"]

    # Second attempt is rejected; still only one expense
    assert client.post(f"/api/occurrences/{occ['id']}/spend", headers=h).status_code == 409
    assert client.get("/api/expenses", headers=h).json()["total"] == 1

    s = safe(client, h)
    assert s["actual_expenses_paise"] == 3500
    assert s["reserved_upcoming_paise"] == reserved_before - 3000  # not double-counted


def test_db_unique_index_blocks_second_expense_for_same_occurrence(client, budget_user, db):
    """Even if the status check were bypassed (race), the DB refuses a second linked expense."""
    from pymongo.errors import DuplicateKeyError

    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[0]
    client.post(f"/api/occurrences/{occ['id']}/spend", headers=h)
    from bson import ObjectId
    try:
        asyncio.run(db.expenses.insert_one({"occurrence_id": ObjectId(occ["id"]), "amount_paise": 1}))
        raised = False
    except DuplicateKeyError:
        raised = True
    assert raised


def test_cannot_spend_skipped_occurrence(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[0]
    client.post(f"/api/occurrences/{occ['id']}/skip", headers=h)
    assert client.post(f"/api/occurrences/{occ['id']}/spend", headers=h).status_code == 409


def test_spending_future_occurrence_is_dated_today(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    future = occurrences(client, h)[5]
    body = client.post(f"/api/occurrences/{future['id']}/spend", headers=h).json()
    assert client.get(f"/api/expenses/{body['expense_id']}", headers=h).json()["date"] == "2026-11-15"


def test_deleting_linked_expense_reverts_occurrence(client, budget_user):
    h = budget_user["headers"]
    make_tea(client, h)
    occ = occurrences(client, h)[0]
    body = client.post(f"/api/occurrences/{occ['id']}/spend", headers=h).json()
    client.delete(f"/api/expenses/{body['expense_id']}", headers=h)
    again = next(o for o in occurrences(client, h) if o["id"] == occ["id"])
    assert again["status"] == "planned" and again["expense_id"] is None


def test_pause_removes_future_plans_and_resume_restores(client, budget_user):
    h = budget_user["headers"]
    rule = make_tea(client, h)
    occurrences(client, h)
    assert client.post(f"/api/routines/{rule['id']}/pause", headers=h).json()["active"] is False
    assert safe(client, h)["reserved_upcoming_paise"] == 0
    assert occurrences(client, h) == []
    client.post(f"/api/routines/{rule['id']}/resume", headers=h)
    assert safe(client, h)["reserved_upcoming_paise"] == 16 * 3000


def test_edit_routine_updates_future_plans(client, budget_user):
    h = budget_user["headers"]
    rule = make_tea(client, h)
    occ = occurrences(client, h)
    client.post(f"/api/occurrences/{occ[0]['id']}/spend", headers=h)  # history must be kept
    res = client.put(f"/api/routines/{rule['id']}", json={**TEA, "amount_paise": 4000}, headers=h)
    assert res.status_code == 200 and res.json()["start_date"] == "2026-11-15"
    after = occurrences(client, h)
    assert len(after) == 16
    assert after[0]["status"] == "spent" and after[0]["amount_paise"] == 3000
    assert all(o["amount_paise"] == 4000 for o in after[1:])


def test_delete_routine_keeps_history(client, budget_user):
    h = budget_user["headers"]
    rule = make_tea(client, h)
    occ = occurrences(client, h)
    client.post(f"/api/occurrences/{occ[0]['id']}/spend", headers=h)
    client.post(f"/api/occurrences/{occ[1]['id']}/skip", headers=h)
    assert client.delete(f"/api/routines/{rule['id']}", headers=h).status_code == 204
    left = occurrences(client, h)
    assert {o["status"] for o in left} == {"spent", "skipped"} and len(left) == 2
    assert client.get("/api/expenses", headers=h).json()["total"] == 1


def test_routines_are_private(client, budget_user, other_user):
    h, oh = budget_user["headers"], other_user["headers"]
    rule = make_tea(client, h)
    occ = occurrences(client, h)[0]
    assert client.get("/api/routines", headers=oh).json() == []
    assert occurrences(client, oh) == []
    assert client.put(f"/api/routines/{rule['id']}", json=TEA, headers=oh).status_code == 404
    assert client.delete(f"/api/routines/{rule['id']}", headers=oh).status_code == 404
    assert client.post(f"/api/occurrences/{occ['id']}/spend", headers=oh).status_code == 404
    assert client.post(f"/api/occurrences/{occ['id']}/skip", headers=oh).status_code == 404
    assert client.get("/api/expenses", headers=oh).json()["total"] == 0
