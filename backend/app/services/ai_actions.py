"""Natural-language actions: interpret -> validate -> show proposal -> user confirms -> execute.

The AI only fills in an `ActionAI` form. The backend validates every field with the same
Pydantic models used by the normal API, checks that referenced records belong to the user,
and stores a *proposal*. Nothing changes until the user confirms, and a proposal can be
executed at most once (atomic status change).
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError
from pymongo import ReturnDocument

from app.ai import prompts
from app.ai.provider import AIProvider, AIUnavailable
from app.schemas.ai import ActionAI, ProposalOut, SummaryLine
from app.schemas.expense import ExpenseIn
from app.schemas.income import IncomeIn
from app.schemas.routine import RoutineIn
from app.services import expense_service, income_service, occurrence_service, routine_service
from app.services.assistant_tools import CATEGORY_LABELS
from app.utils import dates
from app.utils.categorize import suggest_category
from app.utils.ids import parse_object_id
from app.utils.money import MAX_AMOUNT_PAISE, format_inr

log = logging.getLogger(__name__)
PROPOSAL_TTL = timedelta(minutes=15)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_AMOUNT = r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d{1,2})?)"


class Invalid(Exception):
    pass


def _paise(rupees: float | None) -> int:
    if rupees is None or rupees <= 0:
        raise Invalid("I couldn't find an amount. Try something like \"Add ₹150 for lunch today\".")
    paise = int(round(rupees * 100))
    if paise > MAX_AMOUNT_PAISE:
        raise Invalid("That amount looks too large.")
    return paise


def _resolve_date(value: str | None, today: date) -> date:
    if not value or value.lower() == "today":
        return today
    if value.lower() == "yesterday":
        return today - timedelta(days=1)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Invalid(f"I couldn't understand the date \"{value}\".")


def _day_label(d: date, today: date) -> str:
    if d == today:
        return f"Today, {d:%d %b}"
    if d == today - timedelta(days=1):
        return f"Yesterday, {d:%d %b}"
    return f"{d:%a, %d %b %Y}"


def _first_error(e: ValidationError) -> str:
    return e.errors()[0]["msg"].removeprefix("Value error, ")


# ---------- Rule-based interpreter (used when AI is not configured) ----------

def rule_interpret(text: str, routines: list[dict], upcoming: list[dict]) -> ActionAI:
    t = text.lower().strip().rstrip(".!")
    when = "yesterday" if "yesterday" in t else "today"

    m = re.search(rf"\b(?:received|got|earned)\s+{_AMOUNT}\s*(?:as|of|from|for)?\s*(.*)", t)
    if m:
        source = re.sub(r"\b(today|yesterday)\b", "", m.group(2)).strip(" .") or "Other"
        source = source[:1].upper() + source[1:]
        planned = bool(re.search(r"pocket money|allowance", t))
        return ActionAI(action="add_income", amount_rupees=float(m.group(1).replace(",", "")), source=source[:60],
                        date=when, counts_as_planned=planned)

    if t.startswith("skip"):
        for o in upcoming:
            if o["name"].lower() in t or any(w in t for w in o["name"].lower().split() if len(w) > 3):
                return ActionAI(action="skip_occurrence", occurrence_id=o["id"])
        return ActionAI(action="unsupported", reason="I couldn't find a matching planned expense in the next two weeks.")

    m = re.search(rf"\b(?:change|set|update|make)\b.*\bto\s+{_AMOUNT}", t)
    if m:
        best, best_score = None, 0
        for r in routines:
            score = 0
            if r["name"].lower() in t:
                score += 3
            if r["weekday"] is not None and WEEKDAYS[r["weekday"]] in t:
                score += 2
            if r["category"].replace("_", " ") in t:
                score += 1
            if score > best_score:
                best, best_score = r, score
        if best:
            return ActionAI(action="update_routine_amount", routine_id=best["id"], amount_rupees=float(m.group(1).replace(",", "")))
        return ActionAI(action="unsupported", reason="I couldn't tell which recurring expense to change.")

    m = re.search(rf"\b(?:add|spent|paid|log)\s+{_AMOUNT}\s*(?:rupees)?\s*(?:for|on|at)?\s*(.*)", t)
    if m:
        desc = re.sub(r"\b(today|yesterday)\b", "", m.group(2)).strip(" .") or "Expense"
        return ActionAI(action="add_expense", amount_rupees=float(m.group(1).replace(",", "")),
                        description=desc[:1].upper() + desc[1:120], category=suggest_category(desc), date=when)

    return ActionAI(action="unsupported", reason="I can add expenses or income, change a recurring expense's amount, or skip a planned date.")


# ---------- Validation: ActionAI -> stored proposal ----------

async def _build(db, user_id, a: ActionAI, today: date, routines: list[dict], upcoming: list[dict]) -> tuple[str, dict, list[SummaryLine]]:
    if a.action == "add_expense":
        description = (a.description or "Expense").strip()[:120] or "Expense"
        description = description[:1].upper() + description[1:]
        try:
            exp = ExpenseIn(amount_paise=_paise(a.amount_rupees), category=a.category or suggest_category(description),
                            description=description, date=_resolve_date(a.date, today), payment_method="upi")
        except ValidationError as e:
            raise Invalid(_first_error(e))
        params = exp.model_dump(mode="json")
        lines = [SummaryLine(label="Amount", value=format_inr(exp.amount_paise)),
                 SummaryLine(label="Category", value=CATEGORY_LABELS[exp.category]),
                 SummaryLine(label="Description", value=exp.description),
                 SummaryLine(label="Date", value=_day_label(exp.date, today))]
        return "Add expense", params, lines

    if a.action == "add_income":
        src = (a.source or "Other").strip()[:60] or "Other"
        src = src[:1].upper() + src[1:]
        planned = a.counts_as_planned if a.counts_as_planned is not None else bool(re.search(r"pocket money|allowance", src, re.I))
        try:
            inc = IncomeIn(amount_paise=_paise(a.amount_rupees), source=src, date=_resolve_date(a.date, today),
                           counts_as_planned=planned)
        except ValidationError as e:
            raise Invalid(_first_error(e))
        lines = [SummaryLine(label="Amount", value=format_inr(inc.amount_paise)), SummaryLine(label="Source", value=inc.source),
                 SummaryLine(label="Date", value=_day_label(inc.date, today)),
                 SummaryLine(label="Counts as", value="Part of monthly budget (not added again)" if planned else "Extra income")]
        return "Add income", inc.model_dump(mode="json"), lines

    if a.action == "update_routine_amount":
        r = next((x for x in routines if x["id"] == a.routine_id), None)
        if r is None:
            raise Invalid("I couldn't find that recurring expense.")
        new_amount = _paise(a.amount_rupees)
        lines = [SummaryLine(label="Recurring expense", value=r["name"]), SummaryLine(label="Current amount", value=format_inr(r["amount_paise"])),
                 SummaryLine(label="New amount", value=format_inr(new_amount)),
                 SummaryLine(label="Applies to", value="Upcoming planned expenses")]
        return f"Change “{r['name']}” amount", {"routine_id": r["id"], "amount_paise": new_amount}, lines

    if a.action == "skip_occurrence":
        o = next((x for x in upcoming if x["id"] == a.occurrence_id), None)
        if o is None:
            raise Invalid("I couldn't find that planned expense.")
        lines = [SummaryLine(label="Planned expense", value=o["name"]),
                 SummaryLine(label="Date", value=_day_label(date.fromisoformat(o["date"]), today)),
                 SummaryLine(label="Amount freed up", value=format_inr(o["amount_paise"]))]
        return f"Skip “{o['name']}”", {"occurrence_id": o["id"]}, lines

    raise Invalid(a.reason or "I can't do that yet.")


async def _context_lists(db, user_id, today: date) -> tuple[list[dict], list[dict]]:
    rdocs = await db.recurring_rules.find({"user_id": user_id, "active": True}).to_list(None)
    routines = [{"id": str(r["_id"]), "name": r["name"], "amount_paise": r["amount_paise"], "category": r["category"],
                 "frequency": r["frequency"], "weekday": r.get("weekday"), "day_of_month": r.get("day_of_month")} for r in rdocs]
    occ = await occurrence_service.list_occurrences(db, user_id, today, today + timedelta(days=13), "planned")
    upcoming = [{"id": o.id, "name": o.name, "date": o.scheduled_date.isoformat(), "amount_paise": o.amount_paise} for o in occ]
    return routines, upcoming


def _ai_prompt(text: str, today: date, routines: list[dict], upcoming: list[dict]) -> str:
    def rp(r):
        sched = r["frequency"] + (f" on {WEEKDAYS[r['weekday']]}" if r["weekday"] is not None else "") + \
            (f" on day {r['day_of_month']}" if r["day_of_month"] else "")
        return f"- id={r['id']} | {r['name']} | ₹{r['amount_paise'] / 100:g} | {r['category']} | {sched}"
    lines = [f"TODAY: {today.isoformat()} ({WEEKDAYS[today.weekday()]})",
             f"CATEGORIES: {', '.join(CATEGORY_LABELS)}",
             "ROUTINES:", *([rp(r) for r in routines] or ["(none)"]),
             "UPCOMING (next 14 days):",
             *([f"- id={o['id']} | {o['name']} | {o['date']} | ₹{o['amount_paise'] / 100:g}" for o in upcoming] or ["(none)"]),
             f"REQUEST: {text}"]
    return "\n".join(lines)


def _out(doc: dict) -> ProposalOut:
    return ProposalOut(id=str(doc["_id"]), status=doc["status"], action=doc["action"], title=doc["title"],
                       lines=[SummaryLine(**line) for line in doc["lines"]], expires_at=doc.get("expires_at"),
                       interpreted_by=doc["interpreted_by"], result=doc.get("result"), message=doc.get("message"))


async def propose(db, user_id, text: str, ai: AIProvider | None) -> ProposalOut:
    today = dates.app_today()
    routines, upcoming = await _context_lists(db, user_id, today)
    action, interpreted_by = None, "rules"
    if ai:
        try:
            action = await ai.generate_json(system=prompts.ACTION, prompt=_ai_prompt(text, today, routines, upcoming), schema=ActionAI)
            interpreted_by = "ai"
        except AIUnavailable as e:
            log.warning("AI action interpretation failed: %s", e)
    if action is None:
        action = rule_interpret(text, routines, upcoming)
    try:
        title, params, lines = await _build(db, user_id, action, today, routines, upcoming)
    except Invalid as e:
        return ProposalOut(status="unsupported", action=action.action, title="I couldn't turn that into an action",
                           message=str(e), interpreted_by=interpreted_by)
    now = dates.utc_now()
    doc = {"user_id": user_id, "action": action.action, "params": params, "title": title,
           "lines": [line.model_dump() for line in lines], "status": "proposed", "interpreted_by": interpreted_by,
           "request_text": text[:300], "created_at": now, "expires_at": now + PROPOSAL_TTL}
    result = await db.ai_proposals.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _out(doc)


async def _execute(db, user_id, action: str, params: dict) -> tuple[dict, str]:
    """Re-validates stored params and runs the normal service functions."""
    if action == "add_expense":
        exp = await expense_service.create_expense(db, user_id, ExpenseIn(**params))
        return {"expense_id": exp.id}, f"Added {format_inr(exp.amount_paise)} for {exp.description}."
    if action == "add_income":
        inc = await income_service.create_income(db, user_id, IncomeIn(**params))
        return {"income_id": inc.id}, f"Added {format_inr(inc.amount_paise)} income from {inc.source}."
    if action == "update_routine_amount":
        current = await routine_service.get_routine(db, user_id, params["routine_id"])
        data = RoutineIn(**{**current.model_dump(include=set(RoutineIn.model_fields)), "amount_paise": params["amount_paise"]})
        updated = await routine_service.update_routine(db, user_id, params["routine_id"], data)
        return {"routine_id": updated.id}, f"“{updated.name}” is now {format_inr(updated.amount_paise)}."
    if action == "skip_occurrence":
        occ = await occurrence_service.skip(db, user_id, params["occurrence_id"])
        return {"occurrence_id": occ.id}, f"Skipped “{occ.name}”. {format_inr(occ.amount_paise)} is free to use again."
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown action")


async def confirm(db, user_id, proposal_id: str) -> ProposalOut:
    pid = parse_object_id(proposal_id, "Proposal")
    doc = await db.ai_proposals.find_one({"_id": pid, "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if doc["status"] != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This proposal was already {doc['status']}")
    expires = doc["expires_at"] if doc["expires_at"].tzinfo else doc["expires_at"].replace(tzinfo=timezone.utc)
    if expires < dates.utc_now():
        raise HTTPException(status.HTTP_409_CONFLICT, "This proposal expired. Please ask again.")
    # Claim atomically so a double-click can't execute it twice.
    claimed = await db.ai_proposals.find_one_and_update({"_id": pid, "user_id": user_id, "status": "proposed"},
                                                        {"$set": {"status": "executing"}}, return_document=ReturnDocument.AFTER)
    if claimed is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This proposal is already being processed")
    try:
        result, message = await _execute(db, user_id, doc["action"], doc["params"])
    except (ValidationError, HTTPException) as e:
        await db.ai_proposals.update_one({"_id": pid}, {"$set": {"status": "proposed"}})
        if isinstance(e, ValidationError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _first_error(e))
        raise
    except Exception:
        await db.ai_proposals.update_one({"_id": pid}, {"$set": {"status": "proposed"}})
        raise
    done = await db.ai_proposals.find_one_and_update(
        {"_id": pid}, {"$set": {"status": "executed", "result": result, "message": message, "executed_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER)
    return _out(done)


async def cancel(db, user_id, proposal_id: str) -> ProposalOut:
    pid = parse_object_id(proposal_id, "Proposal")
    doc = await db.ai_proposals.find_one_and_update({"_id": pid, "user_id": user_id, "status": "proposed"},
                                                    {"$set": {"status": "cancelled"}}, return_document=ReturnDocument.AFTER)
    if doc is None:
        exists = await db.ai_proposals.find_one({"_id": pid, "user_id": user_id})
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
        raise HTTPException(status.HTTP_409_CONFLICT, f"This proposal was already {exists['status']}")
    return _out(doc)
