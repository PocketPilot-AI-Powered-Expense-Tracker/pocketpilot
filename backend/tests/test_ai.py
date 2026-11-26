"""AI features: grounded answers, confirm-before-change actions, insights and reports."""
import datetime as dt

from app.ai.guard import amounts_in_text, only_known_amounts
from app.ai.provider import AIUnavailable
from app.schemas.ai import ActionAI, InsightTip, InsightTips, ReportText, RoutePlan

EXP = {"category": "food", "description": "Lunch", "date": "2026-11-10"}


def add_expense(client, h, amount, **kw):
    res = client.post("/api/expenses", json={**EXP, "amount_paise": amount, **kw}, headers=h)
    assert res.status_code == 201, res.text
    return res.json()


def ask(client, h, q):
    res = client.post("/api/ai/ask", json={"question": q}, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def facts(body):
    return {f["label"]: f for f in body["facts"]}


def safe(client, h):
    return client.get("/api/analytics/safe-to-spend", headers=h).json()


def counts(client, h):
    return (client.get("/api/expenses", headers=h).json()["total"], client.get("/api/income", headers=h).json()["total"])


# ---------- guard ----------

def test_guard_detects_amounts():
    assert amounts_in_text("You can spend ₹1,250.50 or Rs. 30 today, about 200 rupees") == [125050, 3000, 20000]
    assert only_known_amounts("Spend ₹181 today", {18118})  # rounding to the rupee is fine
    assert not only_known_amounts("Spend ₹500 today", {18118})
    assert only_known_amounts("No amounts here, 27 days left", set())


# ---------- assistant without AI ----------

def test_assistant_without_ai_uses_engine_numbers(client, budget_user):
    h = budget_user["headers"]
    add_expense(client, h, 30000)
    body = ask(client, h, "How much money can I spend today?")
    s = safe(client, h)
    assert body["tool"] == "safe_to_spend" and body["answered_by"] == "rules" and "not configured" in body["notice"]
    assert facts(body)["Safe to spend today"]["paise"] == s["safe_to_spend_today_paise"]


def test_category_question(client, budget_user):
    h = budget_user["headers"]
    add_expense(client, h, 30000)
    add_expense(client, h, 12000, description="Snacks")
    add_expense(client, h, 5000, category="transportation", description="Auto")
    body = ask(client, h, "How much did I spend on food this month?")
    assert body["tool"] == "category_spending"
    assert facts(body)["Food spending this month"]["paise"] == 42000


def test_affordability_verdicts(client, budget_user):
    h = budget_user["headers"]
    s = safe(client, h)
    small = ask(client, h, "Can I afford a ₹100 purchase?")
    assert small["verdict"] == "yes"
    medium = ask(client, h, f"Can I afford ₹{(s['safe_to_spend_today_paise'] // 100) + 500}?")
    assert medium["verdict"] == "yes_with_tradeoff"
    big = ask(client, h, "Can I afford ₹50,000?")
    assert big["verdict"] == "no"


def test_other_questions_route_to_tools(client, budget_user):
    h = budget_user["headers"]
    add_expense(client, h, 30000)
    assert ask(client, h, "What is my biggest expense category?")["tool"] == "top_category"
    assert ask(client, h, "How much should I save every week?")["tool"] == "savings_plan"
    assert ask(client, h, "How much money will I have left at the end of the month?")["tool"] == "end_of_month"
    assert ask(client, h, "Why am I spending more this month?")["tool"] == "spending_change"


# ---------- assistant with AI ----------

def test_ai_explains_verified_numbers(client, budget_user, fake_ai):
    h = budget_user["headers"]
    s = safe(client, h)
    fake_ai.json_responses = [RoutePlan(tool="safe_to_spend")]
    rupees = s["safe_to_spend_today_paise"] // 100
    fake_ai.text_responses = [f"You can spend about ₹{rupees:,} today. Nice work staying on plan!"]
    body = ask(client, h, "how much today?")
    assert body["answered_by"] == "ai" and body["notice"] is None
    assert body["answer"].startswith("You can spend about")


def test_ai_invented_number_is_rejected(client, budget_user, fake_ai):
    h = budget_user["headers"]
    fake_ai.json_responses = [RoutePlan(tool="safe_to_spend")]
    fake_ai.text_responses = ["You can spend ₹9,99,999 today!"]
    body = ask(client, h, "how much today?")
    assert body["answered_by"] == "rules" and "couldn't verify" in body["notice"]
    assert "9,99,999" not in body["answer"]


def test_ai_failure_falls_back(client, budget_user, fake_ai):
    fake_ai.json_responses = [AIUnavailable("down")]
    body = ask(client, budget_user["headers"], "How much can I spend today?")
    assert body["answered_by"] == "rules" and body["tool"] == "safe_to_spend"


def test_ai_never_receives_personal_details(client, budget_user, fake_ai):
    h = budget_user["headers"]
    add_expense(client, h, 30000, description="Secret Cafe Koramangala", notes="birthday gift for Priya")
    fake_ai.json_responses = [RoutePlan(tool="overview"), InsightTips(tips=[])]
    fake_ai.text_responses = ["All good."]
    ask(client, h, "How am I doing?")
    client.get("/api/ai/insights", headers=h)
    sent = " ".join(fake_ai.prompts)
    for secret in ("Secret Cafe", "Priya", "asha@example.com", "Asha"):
        assert secret not in sent


# ---------- natural-language actions ----------

def propose(client, h, text):
    res = client.post("/api/ai/actions/propose", json={"text": text}, headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def test_add_expense_needs_confirmation_and_runs_once(client, budget_user):
    h = budget_user["headers"]
    p = propose(client, h, "Add ₹150 for lunch today.")
    assert p["status"] == "proposed" and p["action"] == "add_expense" and p["interpreted_by"] == "rules"
    assert {line["label"]: line["value"] for line in p["lines"]}["Amount"] == "₹150"
    assert counts(client, h) == (0, 0)  # nothing changed yet

    done = client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h)
    assert done.status_code == 200 and done.json()["status"] == "executed"
    exp = client.get(f"/api/expenses/{done.json()['result']['expense_id']}", headers=h).json()
    assert (exp["amount_paise"], exp["category"], exp["date"]) == (15000, "food", "2026-11-15")
    assert client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h).status_code == 409
    assert counts(client, h) == (1, 0)


def test_received_pocket_money_is_not_double_counted(client, budget_user):
    h = budget_user["headers"]
    before = safe(client, h)["total_income_paise"]
    p = propose(client, h, "I received ₹2,000 pocket money.")
    assert p["action"] == "add_income"
    client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h)
    inc = client.get("/api/income", headers=h).json()["items"][0]
    assert inc["amount_paise"] == 200000 and inc["counts_as_planned"] is True
    assert safe(client, h)["total_income_paise"] == before


def test_change_sunday_food_routine(client, budget_user):
    h = budget_user["headers"]
    r = client.post("/api/routines", json={"name": "Outside food", "amount_paise": 20000, "category": "food",
                                           "frequency": "weekly", "weekday": 6}, headers=h).json()
    p = propose(client, h, "Change my Sunday food budget to ₹250.")
    assert p["action"] == "update_routine_amount", p
    client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h)
    assert client.get(f"/api/routines/{r['id']}", headers=h).json()["amount_paise"] == 25000


def test_skip_planned_movie(client, budget_user):
    h = budget_user["headers"]
    client.post("/api/routines", json={"name": "Movie", "amount_paise": 30000, "category": "entertainment",
                                       "frequency": "monthly", "day_of_month": 20}, headers=h)
    reserved = safe(client, h)["reserved_upcoming_paise"]
    p = propose(client, h, "Skip my planned movie expense this week.")
    assert p["action"] == "skip_occurrence", p
    client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h)
    assert safe(client, h)["reserved_upcoming_paise"] == reserved - 30000


def test_ai_proposal_is_validated(client, budget_user, other_user, fake_ai):
    h = budget_user["headers"]
    # future date
    fake_ai.json_responses = [ActionAI(action="add_expense", amount_rupees=100, category="food", description="x", date="2026-12-01")]
    assert propose(client, h, "add 100 tomorrow")["status"] == "unsupported"
    # negative amount
    fake_ai.json_responses = [ActionAI(action="add_expense", amount_rupees=-5, description="x")]
    assert propose(client, h, "add -5")["status"] == "unsupported"
    # someone else's routine id
    other_rule = client.post("/api/routines", json={"name": "Gym", "amount_paise": 5000, "category": "personal_care",
                                                    "frequency": "daily"}, headers=other_user["headers"]).json()
    fake_ai.json_responses = [ActionAI(action="update_routine_amount", routine_id=other_rule["id"], amount_rupees=1)]
    assert propose(client, h, "change gym to 1")["status"] == "unsupported"
    assert client.get(f"/api/routines/{other_rule['id']}", headers=other_user["headers"]).json()["amount_paise"] == 5000
    assert counts(client, h) == (0, 0)


def test_ai_interpreted_proposal(client, budget_user, fake_ai):
    h = budget_user["headers"]
    fake_ai.json_responses = [ActionAI(action="add_expense", amount_rupees=99.5, category="transportation",
                                       description="Metro", date="2026-11-14")]
    p = propose(client, h, "metro yesterday 99.50")
    assert p["interpreted_by"] == "ai" and p["status"] == "proposed"
    client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h)
    exp = client.get("/api/expenses", headers=h).json()["items"][0]
    assert (exp["amount_paise"], exp["category"], exp["date"]) == (9950, "transportation", "2026-11-14")


def test_cancel_and_isolation_and_expiry(client, budget_user, other_user, monkeypatch):
    h = budget_user["headers"]
    p = propose(client, h, "Add ₹50 for tea")
    assert client.post(f"/api/ai/actions/{p['id']}/confirm", headers=other_user["headers"]).status_code == 404
    assert client.post(f"/api/ai/actions/{p['id']}/cancel", headers=h).json()["status"] == "cancelled"
    assert client.post(f"/api/ai/actions/{p['id']}/confirm", headers=h).status_code == 409

    from app.utils import dates
    p2 = propose(client, h, "Add ₹50 for tea")
    later = dates.utc_now() + dt.timedelta(minutes=20)
    monkeypatch.setattr(dates, "utc_now", lambda: later)
    res = client.post(f"/api/ai/actions/{p2['id']}/confirm", headers=h)
    assert res.status_code == 409 and "expired" in res.json()["detail"]
    assert counts(client, h) == (0, 0)


def test_unclear_request_is_unsupported(client, budget_user):
    p = propose(client, budget_user["headers"], "Book me a flight to Goa")
    assert p["status"] == "unsupported" and p["id"] is None


# ---------- insights ----------

def test_insights_signals(client, budget_user):
    h = budget_user["headers"]
    for i in range(6):
        add_expense(client, h, 3000, description=f"Chai {i}", date=f"2026-11-0{i + 1}")
    add_expense(client, h, 20000, date="2026-10-05")
    add_expense(client, h, 60000, date="2026-11-12")
    body = client.get("/api/ai/insights", headers=h).json()
    kinds = {i["kind"] for i in body["insights"]}
    assert "small_expenses" in kinds and "category_up" in kinds
    small = next(i for i in body["insights"] if i["kind"] == "small_expenses")
    assert "6 purchases" in small["fact"] and "₹180" in small["fact"] and small["tip_by"] == "rules"


def test_insight_tips_from_ai_are_guarded_and_cached(client, budget_user, fake_ai):
    h = budget_user["headers"]
    for i in range(6):
        add_expense(client, h, 3000, description=f"Chai {i}", date=f"2026-11-0{i + 1}")
    fake_ai.json_responses = [InsightTips(tips=[InsightTip(id="s1", tip="Try carrying a flask — it adds up to ₹5,000!"),
                                                InsightTip(id="s2", tip="Put the saved money aside right away.")])]
    first = client.get("/api/ai/insights", headers=h).json()["insights"]
    by_id = {i["id"]: i for i in first}
    assert by_id["s1"]["tip_by"] == "rules"  # invented ₹5,000 was rejected
    assert by_id.get("s2", {}).get("tip_by") in ("ai", None)
    calls = len(fake_ai.prompts)
    client.get("/api/ai/insights", headers=h)  # same data -> cached, no new AI call
    assert len(fake_ai.prompts) == calls


# ---------- monthly report ----------

def test_report_numbers_match_engine(client, budget_user):
    h = budget_user["headers"]
    add_expense(client, h, 30000)
    add_expense(client, h, 20000, date="2026-10-10")
    client.post("/api/routines", json={"name": "Movie", "amount_paise": 30000, "category": "entertainment",
                                       "frequency": "monthly", "day_of_month": 20}, headers=h)
    r = client.get("/api/ai/report", headers=h).json()
    s = safe(client, h)
    assert r["totals"]["expenses_paise"] == s["actual_expenses_paise"] == 30000
    assert r["totals"]["remaining_paise"] == s["remaining_budget_paise"]
    assert r["top_category"]["category"] == "food"
    assert r["planned_vs_actual"]["planned_paise"] == 30000
    assert r["upcoming"]["reserved_paise"] == 30000
    assert r["comparison"]["basis"] == "same point last month" and r["comparison"]["previous_total_paise"] == 20000
    assert r["text"]["written_by"] == "rules" and r["text"]["headline"]

    last = client.get("/api/ai/report", params={"offset": 1}, headers=h).json()
    assert last["period"]["start"] == "2026-10-01" and last["totals"]["expenses_paise"] == 20000
    assert last["period"]["is_current"] is False and last["upcoming"]["reserved_paise"] == 0


def test_report_ai_text_guarded(client, budget_user, fake_ai):
    h = budget_user["headers"]
    add_expense(client, h, 30000)
    fake_ai.json_responses = [ReportText(headline="Great month", summary="You spent ₹300 on food.", recommendations=["Keep going."])]
    assert client.get("/api/ai/report", headers=h).json()["text"]["written_by"] == "ai"

    add_expense(client, h, 1000, description="More")  # data changed -> new AI call
    fake_ai.json_responses = [ReportText(headline="Wow", summary="You saved ₹12,345!", recommendations=[])]
    text = client.get("/api/ai/report", headers=h).json()["text"]
    assert text["written_by"] == "rules" and "12,345" not in text["summary"]


# ---------- safety ----------

def test_ai_endpoints_require_auth_and_are_rate_limited(client, budget_user, monkeypatch):
    assert client.post("/api/ai/ask", json={"question": "hi there"}).status_code == 401
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "AI_RATE_LIMIT_PER_10_MIN", 2)
    h = budget_user["headers"]
    assert client.post("/api/ai/ask", json={"question": "today?"}, headers=h).status_code == 200
    assert client.post("/api/ai/ask", json={"question": "today?"}, headers=h).status_code == 200
    assert client.post("/api/ai/ask", json={"question": "today?"}, headers=h).status_code == 429
