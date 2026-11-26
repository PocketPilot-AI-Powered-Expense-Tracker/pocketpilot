"""Pending UPI transaction review: the most important correctness rules."""
import asyncio

from tests.conftest import auth_headers, register

DETECTED = {"amount_paise": 50000, "source_app": "phonepe", "counterparty": "Campus Cafe",
            "transaction_ref": "432112345678", "detected_at": "2026-11-15T11:45:00+05:30"}


def submit(client, h, **patch):
    return client.post("/api/pending-transactions", json={**DETECTED, **patch}, headers=h)


def safe(client, h):
    return client.get("/api/analytics/safe-to-spend", headers=h).json()


def expense_count(client, h):
    return client.get("/api/expenses", headers=h).json()["total"]


def test_detected_transaction_is_pending_and_does_not_affect_budget(client, budget_user):
    h = budget_user["headers"]
    before = safe(client, h)
    res = submit(client, h)
    assert res.status_code == 201, res.text
    t = res.json()["transaction"]
    assert t["status"] == "pending_review" and t["suggested_category"] == "food" and t["ref_last4"] == "5678"
    assert expense_count(client, h) == 0
    assert safe(client, h) == before
    summary = client.get("/api/pending-transactions/summary", headers=h).json()
    assert summary == {"pending_count": 1, "pending_total_paise": 50000}
    dash = client.get("/api/analytics/dashboard", headers=h).json()
    assert dash["pending_review"]["count"] == 1 and dash["summary"]["actual_expenses_paise"] == 0


def test_raw_reference_number_is_not_stored(client, budget_user, db):
    submit(client, budget_user["headers"])
    stored = asyncio.run(db.pending_transactions.find_one({}))
    assert "432112345678" not in str(stored)
    assert stored["ref_last4"] == "5678"


def test_accept_creates_exactly_one_expense(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    before = safe(client, h)
    res = client.post(f"/api/pending-transactions/{t['id']}/accept", json={"category": "food"},
                      headers={**h, "Idempotency-Key": "key-1"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["transaction"]["status"] == "accepted" and not body["replayed"]
    exp = client.get(f"/api/expenses/{body['expense_id']}", headers=h).json()
    assert exp["amount_paise"] == 50000 and exp["source"] == "upi_review" and exp["payment_method"] == "upi"
    assert exp["description"] == "Campus Cafe" and exp["date"] == "2026-11-15" and exp["pending_id"] == t["id"]
    assert safe(client, h)["actual_expenses_paise"] == before["actual_expenses_paise"] + 50000

    # Retry with the same idempotency key -> same result, no new expense
    replay = client.post(f"/api/pending-transactions/{t['id']}/accept", headers={**h, "Idempotency-Key": "key-1"})
    assert replay.status_code == 200 and replay.json()["replayed"] and replay.json()["expense_id"] == body["expense_id"]
    # A different key (e.g. a second tap that isn't a retry) is refused
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", headers={**h, "Idempotency-Key": "key-2"}).status_code == 409
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h).status_code == 409
    assert expense_count(client, h) == 1


def test_db_blocks_second_expense_for_same_pending(client, budget_user, db):
    from bson import ObjectId
    from pymongo.errors import DuplicateKeyError

    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h)
    try:
        asyncio.run(db.expenses.insert_one({"pending_id": ObjectId(t["id"]), "amount_paise": 1}))
        raised = False
    except DuplicateKeyError:
        raised = True
    assert raised


def test_reject_never_affects_budget(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    before = safe(client, h)
    res = client.post(f"/api/pending-transactions/{t['id']}/reject", headers=h)
    assert res.status_code == 200 and res.json()["status"] == "rejected"
    assert expense_count(client, h) == 0
    assert safe(client, h) == before
    # Can't accept or reject again
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h).status_code == 409
    assert client.post(f"/api/pending-transactions/{t['id']}/reject", headers=h).status_code == 409
    assert expense_count(client, h) == 0
    lists = client.get("/api/pending-transactions", params={"status": "rejected"}, headers=h).json()
    assert len(lists["items"]) == 1 and lists["counts"] == {"pending_review": 0, "accepted": 0, "rejected": 1}


def test_restore_rejected_then_accept(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    client.post(f"/api/pending-transactions/{t['id']}/reject", headers=h)
    assert client.post(f"/api/pending-transactions/{t['id']}/restore", headers=h).json()["status"] == "pending_review"
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h).status_code == 200
    assert expense_count(client, h) == 1


def test_edit_and_accept_uses_corrected_details(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h, counterparty="Rahul Sharma", transaction_ref="999988887777").json()["transaction"]
    assert t["suggested_category"] == "other"
    res = client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h, json={
        "amount_paise": 25000, "category": "food", "description": "My half of dinner",
        "date": "2026-11-14", "notes": "Split with Rahul"})
    assert res.status_code == 200, res.text
    exp = client.get(f"/api/expenses/{res.json()['expense_id']}", headers=h).json()
    assert (exp["amount_paise"], exp["category"], exp["description"], exp["date"], exp["notes"]) == \
        (25000, "food", "My half of dinner", "2026-11-14", "Split with Rahul")


def test_invalid_edit_changes_nothing(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", json={"date": "2026-11-20"}, headers=h).status_code == 422
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", json={"amount_paise": 0}, headers=h).status_code == 422
    items = client.get("/api/pending-transactions", headers=h).json()["items"]
    assert items[0]["status"] == "pending_review" and expense_count(client, h) == 0


def test_duplicate_by_transaction_ref(client, budget_user):
    h = budget_user["headers"]
    first = submit(client, h)
    second = submit(client, h, detected_at="2026-11-15T11:46:00+05:30")  # same ref, re-delivered notification
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["duplicate"] and second.json()["transaction"]["id"] == first.json()["transaction"]["id"]
    assert len(client.get("/api/pending-transactions", params={"status": "all"}, headers=h).json()["items"]) == 1


def test_duplicate_after_reject_stays_rejected(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    client.post(f"/api/pending-transactions/{t['id']}/reject", headers=h)
    again = submit(client, h).json()
    assert again["duplicate"] and again["transaction"]["status"] == "rejected"


def test_duplicate_by_notification_hash(client, budget_user):
    h = budget_user["headers"]
    payload = {"transaction_ref": None, "notification_hash": "a" * 64}
    assert submit(client, h, **payload).status_code == 201
    assert submit(client, h, **payload).json()["duplicate"] is True


def test_same_amount_and_date_are_not_treated_as_duplicates(client, budget_user):
    """Two genuine ₹500 payments on the same day must both be kept."""
    h = budget_user["headers"]
    a = submit(client, h, transaction_ref=None, notification_hash="a" * 64)
    b = submit(client, h, transaction_ref=None, notification_hash="b" * 64)
    assert a.status_code == b.status_code == 201
    assert len(client.get("/api/pending-transactions", headers=h).json()["items"]) == 2


def test_submission_needs_a_dedupe_key_and_valid_fields(client, budget_user):
    h = budget_user["headers"]
    assert submit(client, h, transaction_ref=None).status_code == 422
    assert submit(client, h, amount_paise=0).status_code == 422
    assert submit(client, h, source_app="whatsapp").status_code == 422
    assert submit(client, h, detected_at="2026-11-16T12:00:00+05:30").status_code == 422  # future
    assert submit(client, h, detected_at="2026-11-15T11:45:00").status_code == 422  # no timezone


def test_simulator_parses_and_dedupes(client, budget_user):
    h = budget_user["headers"]
    note = {"source_app": "paytm", "title": "Paytm", "text": "Rs.249 paid to Swiggy successfully. Ref: 612345098765",
            "posted_at": "2026-11-15T10:00:00+05:30"}
    res = client.post("/api/pending-transactions/simulate", json=note, headers=h)
    assert res.status_code == 201, res.text
    t = res.json()["transaction"]
    assert (t["amount_paise"], t["counterparty"], t["suggested_category"], t["origin"]) == (24900, "Swiggy", "food", "simulator")
    # Exact same notification delivered twice -> duplicate
    assert client.post("/api/pending-transactions/simulate", json=note, headers=h).json()["duplicate"]


def test_simulator_without_ref_dedupes_by_hash_only(client, budget_user):
    h = budget_user["headers"]
    note = {"source_app": "gpay", "text": "You paid ₹40 to Chai Point", "posted_at": "2026-11-15T09:00:00+05:30"}
    assert client.post("/api/pending-transactions/simulate", json=note, headers=h).status_code == 201
    assert client.post("/api/pending-transactions/simulate", json=note, headers=h).json()["duplicate"]
    # Same text at a different time = a second real tea
    later = {**note, "posted_at": "2026-11-15T11:00:00+05:30"}
    assert client.post("/api/pending-transactions/simulate", json=later, headers=h).json()["duplicate"] is False


def test_simulator_ignores_credits_requests_and_failures(client, budget_user):
    h = budget_user["headers"]
    for text in ["Received ₹1,000 from Mom", "Riya requested ₹300", "Payment of ₹80 to Auto failed"]:
        res = client.post("/api/pending-transactions/simulate", json={"source_app": "phonepe", "text": text}, headers=h)
        assert res.status_code == 422 and "Ignored" in res.json()["detail"]
    assert client.get("/api/pending-transactions/summary", headers=h).json()["pending_count"] == 0


def test_simulator_future_time_is_a_clear_422(client, budget_user):
    note = {"source_app": "gpay", "text": "You paid ₹40 to Chai Point", "posted_at": "2026-11-16T09:00:00+05:30"}
    res = client.post("/api/pending-transactions/simulate", json=note, headers=budget_user["headers"])
    assert res.status_code == 422 and "future" in res.json()["detail"]


def test_deleting_accepted_expense_returns_it_to_review(client, budget_user):
    h = budget_user["headers"]
    t = submit(client, h).json()["transaction"]
    exp_id = client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h).json()["expense_id"]
    client.delete(f"/api/expenses/{exp_id}", headers=h)
    item = client.get("/api/pending-transactions", headers=h).json()["items"][0]
    assert item["status"] == "pending_review" and item["expense_id"] is None
    # ...and it can be accepted again, still exactly one expense
    assert client.post(f"/api/pending-transactions/{t['id']}/accept", headers=h).status_code == 200
    assert expense_count(client, h) == 1


def test_users_cannot_see_or_review_others_transactions(client, budget_user, other_user):
    h, oh = budget_user["headers"], other_user["headers"]
    t = submit(client, h).json()["transaction"]
    assert client.get("/api/pending-transactions", params={"status": "all"}, headers=oh).json()["items"] == []
    for action in ("accept", "reject", "restore"):
        assert client.post(f"/api/pending-transactions/{t['id']}/{action}", headers=oh).status_code == 404
    # The same UPI ref for another user is that user's own record, not a duplicate
    assert submit(client, oh).status_code == 201
    assert client.get("/api/pending-transactions/summary", headers=h).json()["pending_count"] == 1


def test_pending_requires_auth(client):
    assert client.post("/api/pending-transactions", json=DETECTED).status_code == 401
    assert client.get("/api/pending-transactions").status_code == 401
