"""Spending insights and the monthly report.

1. Python detects patterns ("signals") and calculates every number.
2. The AI only writes tips / summary text about those signals.
3. Each AI sentence passes the number guard, otherwise a template is used.
4. AI text is cached per user for 12 hours, keyed by a hash of the underlying numbers.
"""
import hashlib
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from app.ai import prompts
from app.ai.guard import clean_text, only_known_amounts, unknown_amounts
from app.ai.provider import AIProvider, AIUnavailable
from app.schemas.ai import InsightOut, InsightsResponse, InsightTips, ReportText
from app.services import finance_context
from app.services.assistant_tools import CATEGORY_LABELS
from app.services.budget_engine import compare_categories
from app.services.finance_context import FinanceContext
from app.utils.money import format_inr

log = logging.getLogger(__name__)
SMALL_EXPENSE_PAISE = 10000  # under ₹100
DISCRETIONARY = ("food", "entertainment", "shopping")
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------------- Signals (deterministic) ----------------

def build_signals(ctx: FinanceContext) -> list[dict]:
    s = ctx.summary
    signals: list[dict] = []

    def add(kind, severity, title, fact, amounts, tip):
        signals.append({"id": f"s{len(signals) + 1}", "kind": kind, "severity": severity, "title": title,
                        "fact": fact, "amounts": [a for a in amounts if a is not None], "fallback_tip": tip})

    if s.status == "over_budget":
        add("over_budget", "warning", "You've spent more than your income",
            f"Spending is {format_inr(-s.remaining_budget_paise)} over your income of {format_inr(s.total_income_paise)} this month.",
            [s.remaining_budget_paise, s.total_income_paise],
            "Pause non-essential spending for a few days and check the categories below for what to cut.")
    elif s.status == "at_risk":
        add("at_risk", "warning", "Your plans and savings aren't fully covered",
            f"After {format_inr(s.reserved_upcoming_paise)} of planned expenses, you're {format_inr(-s.free_to_spend_paise)} short of your savings target.",
            [s.reserved_upcoming_paise, s.free_to_spend_paise],
            "Skip one or two planned expenses you can live without, or lower your savings target for this month.")
    elif s.status == "watch":
        add("fast_pace", "warning", "Spending faster than the month",
            f"You've used {s.spent_pct}% of your spendable money with {s.elapsed_pct}% of the month gone.",
            [], "Try a couple of no-spend days this week to get back on pace.")

    prev_items = ctx.prev_same_point()
    cur, prev = defaultdict(int), defaultdict(int)
    for e in ctx.expenses:
        cur[e.category] += e.amount_paise
    for e in prev_items:
        prev[e.category] += e.amount_paise
    for c in sorted(cur, key=lambda c: -(cur[c] - prev[c])):
        diff = cur[c] - prev[c]
        if prev[c] > 0 and diff >= 20000 and diff * 100 >= prev[c] * 25:
            pct = diff * 100 // prev[c]
            add("category_up", "warning", f"More on {CATEGORY_LABELS[c].lower()} than usual",
                f"{format_inr(cur[c])} on {CATEGORY_LABELS[c].lower()} so far, up {format_inr(diff)} ({pct}%) from this point last month.",
                [cur[c], diff], f"Set yourself a weekly {CATEGORY_LABELS[c].lower()} limit and check it on Sundays.")
            if sum(1 for x in signals if x["kind"] == "category_up") >= 2:
                break

    small = [e for e in ctx.expenses if e.amount_paise < SMALL_EXPENSE_PAISE and not e.planned]
    if len(small) >= 5:
        total = sum(e.amount_paise for e in small)
        add("small_expenses", "info", "Small expenses are adding up",
            f"{len(small)} purchases under ₹100 this month add up to {format_inr(total)}.",
            [total, SMALL_EXPENSE_PAISE], "Turn the most frequent small buy into a routine so it's planned, or cut it to every other day.")

    if ctx.categories and ctx.categories[0]["pct"] >= 40 and ctx.categories[0]["amount_paise"] >= 50000 and len(ctx.categories) > 1:
        top = ctx.categories[0]
        add("concentration", "info", f"{CATEGORY_LABELS[top['category']]} is most of your spending",
            f"{CATEGORY_LABELS[top['category']]} is {top['pct']}% of your spending ({format_inr(top['amount_paise'])}).",
            [top["amount_paise"]], f"Look for one cheaper swap in {CATEGORY_LABELS[top['category']].lower()} spending, like cooking or carrying snacks once a week.")

    disc = [c for c in ctx.categories if c["category"] in DISCRETIONARY]
    if disc:
        top = disc[0]
        saving = top["amount_paise"] * 20 // 100
        if saving >= 10000:
            add("savings_opportunity", "positive", "A simple way to save more",
                f"Cutting {CATEGORY_LABELS[top['category']].lower()} by 20% would save {format_inr(saving)} this month.",
                [saving, top["amount_paise"]], f"Spend a little less on {CATEGORY_LABELS[top['category']].lower()} and move what you save into savings straight away, so it doesn't get spent.")

    spendable = s.total_income_paise - s.savings_target_paise
    if spendable > 0 and s.reserved_upcoming_paise * 100 >= max(1, s.remaining_budget_paise - s.savings_target_paise) * 40 \
            and s.reserved_upcoming_paise > 0:
        add("commitments", "info", "Lots of money is already planned",
            f"{format_inr(s.reserved_upcoming_paise)} is reserved for {s.upcoming_count} upcoming planned expenses.",
            [s.reserved_upcoming_paise], "Check your recurring expenses and skip any dates you won't need this month.")

    if s.status == "on_track" and s.spent_pct + 10 < s.elapsed_pct and s.actual_expenses_paise > 0:
        add("good_pace", "positive", "Nice pacing",
            f"You've used {s.spent_pct}% of your spendable money with {s.elapsed_pct}% of the month gone.",
            [], "Keep it up, and consider moving a little extra to savings now.")

    order = {"warning": 0, "info": 1, "positive": 2}
    return sorted(signals, key=lambda x: order[x["severity"]])[:5]


# ---------------- Cache ----------------

def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


async def _cached(db, user_id, kind: str, key: str):
    doc = await db.ai_cache.find_one({"user_id": user_id, "kind": kind, "key": key})
    return doc["payload"] if doc else None


async def _store(db, user_id, kind: str, key: str, payload) -> None:
    await db.ai_cache.update_one({"user_id": user_id, "kind": kind},
                                 {"$set": {"key": key, "payload": payload, "created_at": datetime.now(timezone.utc)}},
                                 upsert=True)


# ---------------- Insights ----------------

async def insights(db, user_id, ai: AIProvider | None) -> InsightsResponse:
    ctx = await finance_context.load(db, user_id)
    signals = build_signals(ctx)
    tips: dict[str, str] = {}
    if ai and signals:
        public = [{"id": x["id"], "title": x["title"], "fact": x["fact"]} for x in signals]
        key = _hash(public)
        tips = await _cached(db, user_id, "insights", key) or {}
        if not tips:
            try:
                res = await ai.generate_json(system=prompts.INSIGHTS, prompt=json.dumps({"SIGNALS": public}, ensure_ascii=False),
                                             schema=InsightTips)
                by_id = {x["id"]: x for x in signals}
                tips = {t.id: clean_text(t.tip) for t in res.tips
                        if t.id in by_id and t.tip.strip() and only_known_amounts(t.tip, set(by_id[t.id]["amounts"]))}
                await _store(db, user_id, "insights", key, tips)
            except AIUnavailable as e:
                log.warning("AI insights failed: %s", e)
    out = [InsightOut(id=x["id"], kind=x["kind"], severity=x["severity"], title=x["title"], fact=x["fact"],
                      tip=tips.get(x["id"], x["fallback_tip"]), tip_by="ai" if x["id"] in tips else "rules") for x in signals]
    return InsightsResponse(insights=out, ai_available=ai is not None)


# ---------------- Monthly report ----------------

async def report(db, user_id, offset: int, ai: AIProvider | None) -> dict:
    ctx = await finance_context.load(db, user_id, offset)
    s, p = ctx.summary, ctx.period
    is_current = offset == 0

    occ = await db.planned_occurrences.find(
        {"user_id": user_id, "scheduled_date": {"$gte": p.start.isoformat(), "$lte": p.end.isoformat()}},
        {"amount_paise": 1, "status": 1, "name": 1, "scheduled_date": 1}).to_list(None)
    planned_total = sum(o["amount_paise"] for o in occ if o["status"] != "skipped")
    skipped_total = sum(o["amount_paise"] for o in occ if o["status"] == "skipped")

    compare_items = ctx.prev_same_point() if is_current else ctx.prev_expenses
    prev_total = sum(e.amount_paise for e in compare_items)
    change = s.actual_expenses_paise - prev_total

    weekday = [0] * 7
    days_with_spending = set()
    for e in ctx.expenses:
        weekday[e.date.weekday()] += e.amount_paise
        days_with_spending.add(e.date)
    small = [e for e in ctx.expenses if e.amount_paise < SMALL_EXPENSE_PAISE and not e.planned]
    days_counted = ctx.elapsed_days if is_current else p.total_days
    upcoming = []
    if is_current:
        docs = sorted((o for o in occ if o["status"] == "planned" and o["scheduled_date"] >= ctx.today.isoformat()),
                      key=lambda o: o["scheduled_date"])
        upcoming = [{"name": o["name"], "date": o["scheduled_date"], "amount_paise": o["amount_paise"]} for o in docs[:6]]

    data = {
        "period": {"start": p.start, "end": p.end, "is_current": is_current, "label": f"{p.start:%d %b} – {p.end:%d %b %Y}"},
        "totals": {
            "planned_income_paise": s.planned_income_paise, "extra_income_paise": s.extra_income_paise,
            "total_income_paise": s.total_income_paise, "expenses_paise": s.actual_expenses_paise,
            "remaining_paise": s.remaining_budget_paise, "savings_target_paise": s.savings_target_paise,
            "projected_savings_paise": s.projected_end_balance_paise, "savings_progress_pct": s.savings_progress_pct,
            "status": s.status,
        },
        "categories": ctx.categories,
        "top_category": ctx.categories[0] if ctx.categories else None,
        "planned_vs_actual": {"planned_paise": planned_total, "spent_from_plans_paise": s.planned_spent_paise,
                              "skipped_paise": skipped_total, "unplanned_paise": s.unplanned_spent_paise},
        "comparison": {"basis": "same point last month" if is_current else "previous month",
                       "previous_total_paise": prev_total, "change_paise": change,
                       "change_pct": (change * 100 // prev_total) if prev_total else None,
                       "categories": compare_categories(ctx.expenses, compare_items)[:6]},
        "patterns": {"weekday_totals": [{"day": WEEKDAY_NAMES[i], "amount_paise": weekday[i]} for i in range(7)],
                     "busiest_weekday": WEEKDAY_NAMES[max(range(7), key=lambda i: weekday[i])] if ctx.expenses else None,
                     "avg_per_day_paise": s.actual_expenses_paise // max(1, days_counted),
                     "days_with_spending": len(days_with_spending), "days_counted": days_counted,
                     "small_expenses_count": len(small), "small_expenses_paise": sum(e.amount_paise for e in small)},
        "upcoming": {"reserved_paise": s.reserved_upcoming_paise if is_current else 0, "items": upcoming},
    }
    data["text"] = await _report_text(db, user_id, data, ctx, ai)
    return data


def _fallback_report_text(d: dict, ctx: FinanceContext) -> dict:
    t, c = d["totals"], d["comparison"]
    if t["status"] == "over_budget":
        headline = f"Spending went {format_inr(-t['remaining_paise'])} over income"
    elif d["period"]["is_current"]:
        headline = {"on_track": "On track so far this month", "watch": "Spending a bit fast this month",
                    "at_risk": "Savings target needs attention"}[t["status"]]
    else:
        headline = f"You kept {format_inr(max(0, t['remaining_paise']))} of your income"
    parts = [f"You had {format_inr(t['total_income_paise'])} and spent {format_inr(t['expenses_paise'])}."]
    if d["top_category"]:
        top = d["top_category"]
        parts.append(f"{CATEGORY_LABELS[top['category']]} was your biggest category at {format_inr(top['amount_paise'])} ({top['pct']}%).")
    if c["previous_total_paise"]:
        word = "more" if c["change_paise"] > 0 else "less"
        parts.append(f"That's {format_inr(abs(c['change_paise']))} {word} than {c['basis']}.")
    parts.append(f"Your savings target is {t['savings_progress_pct']}% protected.")
    recs = [x["fallback_tip"] for x in build_signals(ctx)][:3] or ["Keep logging every expense so your numbers stay accurate."]
    return {"headline": headline, "summary": " ".join(parts), "recommendations": recs, "written_by": "rules"}


def _allowed_amounts(d: dict) -> set[int]:
    vals: set[int] = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.endswith("_paise") and isinstance(v, int):
                    vals.add(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return vals


async def _report_text(db, user_id, data: dict, ctx: FinanceContext, ai: AIProvider | None) -> dict:
    fallback = _fallback_report_text(data, ctx)
    if not ai:
        return fallback
    # Compact, human-readable numbers for the model. No names, merchants or notes.
    t = data["totals"]
    brief = {
        "period": data["period"]["label"], "is_current_month": data["period"]["is_current"], "status": t["status"],
        "total_income": format_inr(t["total_income_paise"]), "spent": format_inr(t["expenses_paise"]),
        "remaining": format_inr(t["remaining_paise"]), "savings_target": format_inr(t["savings_target_paise"]),
        "savings_protected_pct": t["savings_progress_pct"],
        "categories": {CATEGORY_LABELS[c["category"]]: format_inr(c["amount_paise"]) for c in data["categories"]},
        "compared_to": data["comparison"]["basis"], "previous_spent": format_inr(data["comparison"]["previous_total_paise"]),
        "change": (f"{format_inr(abs(data['comparison']['change_paise']))} "
                   f"{'more' if data['comparison']['change_paise'] > 0 else 'less'} than {data['comparison']['basis']}"),
        "planned": format_inr(data["planned_vs_actual"]["planned_paise"]),
        "unplanned_spent": format_inr(data["planned_vs_actual"]["unplanned_paise"]),
        "busiest_weekday": data["patterns"]["busiest_weekday"],
        "small_purchases_under_100": data["patterns"]["small_expenses_count"],
        "small_purchases_total": format_inr(data["patterns"]["small_expenses_paise"]),
        "reserved_for_upcoming_plans": format_inr(data["upcoming"]["reserved_paise"]),
    }
    key = _hash(brief)
    cached = await _cached(db, user_id, f"report:{data['period']['start']}", key)
    if cached:
        return cached
    try:
        res = await ai.generate_json(system=prompts.REPORT, prompt=json.dumps({"REPORT DATA": brief}, ensure_ascii=False),
                                     schema=ReportText)
    except AIUnavailable as e:
        log.warning("AI report failed: %s", e)
        return fallback
    allowed = _allowed_amounts(data) | {SMALL_EXPENSE_PAISE}
    pieces = [res.headline, res.summary, *res.recommendations]
    bad = [a for x in pieces for a in unknown_amounts(x, allowed)]
    if bad or not res.summary.strip():
        log.warning("AI report failed number guard (unverified amounts in paise: %s)", bad[:5])
        return {**fallback, "notice": "The AI summary mentioned an amount we couldn't verify, so a calculated summary is shown."}
    text = {"headline": clean_text(res.headline)[:120], "summary": clean_text(res.summary),
            "recommendations": [clean_text(r) for r in res.recommendations if r.strip()][:3], "written_by": "ai"}
    await _store(db, user_id, f"report:{data['period']['start']}", key, text)
    return text
