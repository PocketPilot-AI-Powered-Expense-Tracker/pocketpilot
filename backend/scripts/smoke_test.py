"""End-to-end smoke test against a RUNNING PocketPilot API (local, Atlas-backed, or deployed).

    cd backend
    .venv/bin/python scripts/smoke_test.py http://localhost:8000
    .venv/bin/python scripts/smoke_test.py https://your-api.onrender.com

It creates a throwaway account (smoke-<random>@example.com), exercises the critical
money rules against the real database (unique indexes, duplicate blocking, exactly-once
actions), then DELETES that account and all its data. Exit code 0 = all checks passed.
"""
import secrets
import sys
from datetime import datetime, timezone

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> bool:
    results.append((bool(ok), label))
    print(("  PASS  " if ok else "  FAIL  ") + label, flush=True)
    return bool(ok)


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    print(f"PocketPilot smoke test → {BASE}")

    check(c.get("/api/health").status_code == 200, "API is up")
    ready = c.get("/api/health/ready")
    if not check(ready.status_code == 200, "Database reachable (/api/health/ready)"):
        print("   ", ready.text)
        return 1

    email = f"smoke-{secrets.token_hex(4)}@example.com"
    reg = c.post("/api/auth/register", json={"name": "Smoke Test", "email": email, "password": "smoke1234"})
    if not check(reg.status_code == 201, "Register"):
        print("   ", reg.text)
        return 1
    c.headers["Authorization"] = f"Bearer {reg.json()['access_token']}"
    try:
        run(c)
    finally:
        check(c.delete("/api/auth/me").status_code == 204, "Delete smoke-test account and data")
    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


def run(c: httpx.Client) -> None:
    check(c.get("/api/auth/me").json()["email"].startswith("smoke-"), "Current user")
    check(c.post("/api/budget", json={"monthly_allowance_paise": 800000, "additional_income_paise": 0,
                                      "savings_target_paise": 100000, "period_start_day": 1}).status_code == 201, "Create budget")
    check(c.post("/api/budget", json={"monthly_allowance_paise": 1}).status_code in (409, 422), "Second budget rejected")
    period_start = c.get("/api/analytics/safe-to-spend").json()["period_start"]

    exp = c.post("/api/expenses", json={"amount_paise": 15050, "category": "food", "description": "Smoke lunch",
                                        "date": datetime.now(timezone.utc).date().isoformat()})
    if exp.status_code == 422:  # server "today" (IST) may be a day behind UTC
        exp = c.post("/api/expenses", json={"amount_paise": 15050, "category": "food", "description": "Smoke lunch", "date": period_start})
    check(exp.status_code == 201, "Create expense")
    check(c.get("/api/expenses", params={"q": "smoke"}).json()["total"] == 1, "Search expenses (regex on real DB)")
    s1 = c.get("/api/analytics/safe-to-spend").json()
    check(s1["actual_expenses_paise"] == 15050, "Budget engine counts the expense")

    rule = c.post("/api/routines", json={"name": "Smoke tea", "amount_paise": 3000, "category": "food", "frequency": "daily"}).json()
    o1 = c.get("/api/occurrences").json()
    o2 = c.get("/api/occurrences").json()
    check(len(o1) > 0 and len(o1) == len(o2), "Occurrences generated once (unique index, no duplicates)")
    first = o1[0]["id"]
    check(c.post(f"/api/occurrences/{first}/spend").status_code == 200, "Mark planned expense spent")
    check(c.post(f"/api/occurrences/{first}/spend").status_code == 409, "Second 'spent' rejected (exactly once)")
    if len(o1) > 1:
        check(c.post(f"/api/occurrences/{o1[1]['id']}/skip").status_code == 200, "Skip planned expense")
    check(c.post(f"/api/routines/{rule['id']}/pause").json()["active"] is False, "Pause routine")

    ref = str(secrets.randbelow(9 * 10**11) + 10**11)
    det = {"amount_paise": 50000, "source_app": "gpay", "counterparty": "Smoke Cafe", "transaction_ref": ref,
           "detected_at": datetime.now(timezone.utc).isoformat()}
    spent_before_pending = c.get("/api/analytics/safe-to-spend").json()["actual_expenses_paise"]
    p1 = c.post("/api/pending-transactions", json=det)
    p2 = c.post("/api/pending-transactions", json=det)
    check(p1.status_code == 201 and p2.status_code == 200 and p2.json()["duplicate"], "Duplicate UPI transaction blocked")
    before = c.get("/api/analytics/safe-to-spend").json()["actual_expenses_paise"]
    check(before == spent_before_pending, "Pending payment not counted")
    pid = p1.json()["transaction"]["id"]
    key = {"Idempotency-Key": secrets.token_hex(8)}
    a1 = c.post(f"/api/pending-transactions/{pid}/accept", headers=key)
    a2 = c.post(f"/api/pending-transactions/{pid}/accept", headers=key)
    check(a1.status_code == 200 and a2.status_code == 200 and a2.json()["replayed"], "Accept is idempotent")
    after = c.get("/api/analytics/safe-to-spend").json()["actual_expenses_paise"]
    check(after - before == 50000, "Accepted payment counted exactly once")
    sim = c.post("/api/pending-transactions/simulate", json={"source_app": "phonepe", "text": "₹80 paid to Smoke Auto"})
    if sim.status_code == 201:
        rid = sim.json()["transaction"]["id"]
        check(c.post(f"/api/pending-transactions/{rid}/reject").status_code == 200, "Reject pending payment")
        check(c.get("/api/analytics/safe-to-spend").json()["actual_expenses_paise"] == after, "Rejected payment not counted")

    prop = c.post("/api/ai/actions/propose", json={"text": "Add ₹99 for smoke snacks"}).json()
    check(prop["status"] == "proposed", f"AI/rules action proposal (interpreted by {prop.get('interpreted_by')})")
    if prop.get("id"):
        check(c.post(f"/api/ai/actions/{prop['id']}/confirm").status_code == 200, "Confirm proposal")
        check(c.post(f"/api/ai/actions/{prop['id']}/confirm").status_code == 409, "Proposal runs only once")
    ask = c.post("/api/ai/ask", json={"question": "How much can I spend today?"})
    check(ask.status_code == 200 and ask.json()["facts"], f"Assistant answers (by {ask.json().get('answered_by')})")
    check(c.get("/api/ai/insights").status_code == 200, "Insights")
    check(c.get("/api/ai/report").json()["totals"]["expenses_paise"] == c.get("/api/analytics/safe-to-spend").json()["actual_expenses_paise"],
          "Report totals match the budget engine")
    check(c.get("/api/analytics/dashboard").status_code == 200, "Dashboard")


if __name__ == "__main__":
    sys.exit(main())
