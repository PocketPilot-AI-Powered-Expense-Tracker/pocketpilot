"""Recurring rules (templates) and generation of planned occurrences.

Concepts kept separate:
  recurring_rules      the template ("Tea ₹30 every day")
  planned_occurrences  one scheduled instance (Tea on 4 Nov) — reserves money, is NOT an expense
  expenses             money actually spent

Occurrences are generated lazily for the date range being viewed (never before the
current budget period). Each has a unique (rule_id, original_date) key, so generating
twice never creates duplicates, and a rescheduled or skipped occurrence is never re-created.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError

from app.schemas.routine import RoutineIn, RoutineOut
from app.utils import dates
from app.utils.ids import parse_object_id
from app.utils.serialize import date_str, to_out

MAX_GENERATION_DAYS = 93
# How far back automatic deductions catch up if the app wasn't opened for a while.
AUTO_LOOKBACK_DAYS = 62


def rule_dates(rule: dict, start: date, end: date) -> list[date]:
    """All dates in [start, end] on which the rule fires. Pure function."""
    rule_start = _as_date(rule["start_date"])
    rule_end = _as_date(rule["end_date"]) if rule.get("end_date") else None
    start = max(start, rule_start)
    if rule_end:
        end = min(end, rule_end)
    out, d = [], start
    while d <= end:
        f = rule["frequency"]
        if f == "daily" or (f == "weekly" and d.weekday() == rule["weekday"]) or \
                (f == "monthly" and d.day == rule["day_of_month"]):
            out.append(d)
        d += timedelta(days=1)
    return out


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(v)


def _rule_doc(data: RoutineIn) -> dict:
    d = data.model_dump(exclude={"deduct_this_month"})
    d["start_date"] = date_str(data.start_date or dates.app_today())
    d["end_date"] = date_str(data.end_date) if data.end_date else None
    return d


def _occurrence_doc(user_id, rule: dict, d: date) -> dict:
    return {
        "user_id": user_id,
        "rule_id": rule["_id"],
        "name": rule["name"],
        "amount_paise": rule["amount_paise"],
        "category": rule["category"],
        "payment_method": rule.get("payment_method", "upi"),
        "original_date": date_str(d),
        "scheduled_date": date_str(d),
        "rescheduled": False,
        "status": "planned",
    }


async def _insert_missing(db, user_id, rules: list[dict], start: date, end: date) -> None:
    """Insert occurrences of `rules` in [start, end] that don't exist yet (idempotent)."""
    if not rules or end < start:
        return
    existing = await db.planned_occurrences.find(
        {"user_id": user_id, "rule_id": {"$in": [r["_id"] for r in rules]},
         "original_date": {"$gte": date_str(start), "$lte": date_str(end)}},
        {"rule_id": 1, "original_date": 1},
    ).to_list(None)
    have = {(o["rule_id"], o["original_date"]) for o in existing}
    docs = [_occurrence_doc(user_id, r, d) for r in rules for d in rule_dates(r, start, end)
            if (r["_id"], date_str(d)) not in have]
    if docs:
        try:
            await db.planned_occurrences.insert_many(docs, ordered=False)
        except BulkWriteError as e:
            # Another request generated the same occurrences concurrently: fine.
            if any(err.get("code") != 11000 for err in e.details.get("writeErrors", [])):
                raise


async def ensure_occurrences(db, user_id, start: date, end: date, *, earliest: date) -> None:
    """Create any missing planned occurrences for active rules within [start, end], then
    record any automatic deductions that are due. `earliest` (the current period start)
    stops back-filling old months for tap-to-record expenses."""
    start = max(start, earliest)
    if end >= start:
        if (end - start).days > MAX_GENERATION_DAYS:
            end = start + timedelta(days=MAX_GENERATION_DAYS)
        rules = await db.recurring_rules.find({"user_id": user_id, "active": True}).to_list(None)
        await _insert_missing(db, user_id, rules, start, end)
    await apply_auto_deductions(db, user_id)


async def apply_auto_deductions(db, user_id) -> int:
    """For recurring expenses set to "deduct automatically": every due date up to today
    (looking back at most AUTO_LOOKBACK_DAYS) becomes exactly one real expense.
    Safe to call repeatedly: the unique index on expenses.occurrence_id prevents duplicates.
    Returns how many expenses were created."""
    from pymongo.errors import DuplicateKeyError

    from app.schemas.expense import ExpenseIn
    from app.services import expense_service

    today = dates.app_today()
    rules = await db.recurring_rules.find({"user_id": user_id, "active": True, "deduction_mode": "auto"}).to_list(None)
    if not rules:
        return 0
    await _insert_missing(db, user_id, rules, today - timedelta(days=AUTO_LOOKBACK_DAYS), today)
    due = await db.planned_occurrences.find({
        "user_id": user_id, "rule_id": {"$in": [r["_id"] for r in rules]},
        "status": "planned", "scheduled_date": {"$lte": date_str(today)},
    }).to_list(None)
    created = 0
    for occ in due:
        expense_in = ExpenseIn(amount_paise=occ["amount_paise"], category=occ["category"], description=occ["name"],
                               date=date.fromisoformat(occ["scheduled_date"]),
                               payment_method=occ.get("payment_method", "upi"), notes="Deducted automatically")
        try:
            exp = await expense_service.create_expense(db, user_id, expense_in, source="routine",
                                                       extra={"occurrence_id": occ["_id"], "auto_deducted": True})
            expense_id = parse_object_id(exp.id)
            created += 1
        except DuplicateKeyError:
            existing = await db.expenses.find_one({"occurrence_id": occ["_id"], "user_id": user_id}, {"_id": 1})
            expense_id = existing["_id"]
        await db.planned_occurrences.update_one(
            {"_id": occ["_id"], "user_id": user_id, "status": "planned"},
            {"$set": {"status": "spent", "expense_id": expense_id, "auto_deducted": True}})
    return created


async def deduction_modes(db, user_id) -> dict:
    """rule_id -> "auto" | "manual" for the user's recurring expenses."""
    rules = await db.recurring_rules.find({"user_id": user_id}, {"deduction_mode": 1}).to_list(None)
    return {r["_id"]: r.get("deduction_mode", "manual") for r in rules}


async def sync_current_period(db, user_id) -> None:
    """Make sure this period's occurrences exist and automatic deductions are recorded."""
    from app.services.budget_service import get_budget_doc
    from app.utils.periods import period_containing

    budget = await get_budget_doc(db, user_id)
    period = period_containing(dates.app_today(), budget["period_start_day"] if budget else 1)
    await ensure_occurrences(db, user_id, period.start, period.end, earliest=period.start)


async def _drop_future_planned(db, user_id, rule_id, *, keep_rescheduled: bool) -> None:
    f = {"user_id": user_id, "rule_id": rule_id, "status": "planned",
         "scheduled_date": {"$gte": date_str(dates.app_today())}}
    if keep_rescheduled:
        f["rescheduled"] = False
    await db.planned_occurrences.delete_many(f)


async def _get_rule(db, user_id, rule_id: str) -> dict:
    doc = await db.recurring_rules.find_one({"_id": parse_object_id(rule_id, "Routine"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Routine not found")
    return doc


def passed_due_date_this_month(data: RoutineIn, today: date) -> date | None:
    """For a new monthly expense: this calendar month's due date if it has already passed
    and the chosen start date would otherwise skip it. None if the option doesn't apply."""
    if data.frequency != "monthly" or not data.day_of_month or data.day_of_month >= today.day:
        return None
    due = today.replace(day=data.day_of_month)
    start = data.start_date or today
    if start <= due or (data.end_date and data.end_date < due):
        return None
    return due


async def create_routine(db, user_id, data: RoutineIn) -> RoutineOut:
    from app.schemas.expense import ExpenseIn
    from app.services import expense_service

    today = dates.app_today()
    due = None
    if data.deduct_this_month:
        due = passed_due_date_this_month(data, today)
        if due is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "This month's due date hasn't passed (or is already covered by the start date)")
    now = datetime.now(timezone.utc)
    doc = {"user_id": user_id, **_rule_doc(data), "active": True, "created_at": now, "updated_at": now}
    result = await db.recurring_rules.insert_one(doc)
    doc["_id"] = result.inserted_id
    out = RoutineOut(**to_out(doc))
    if due:
        # This month's amount: one occurrence (already spent) + one expense on the due date.
        auto = data.deduction_mode == "auto"
        occ = {**_occurrence_doc(user_id, doc, due), "status": "spent", "auto_deducted": auto}
        occ_id = (await db.planned_occurrences.insert_one(occ)).inserted_id
        expense = await expense_service.create_expense(
            db, user_id,
            ExpenseIn(amount_paise=data.amount_paise, category=data.category, description=data.name, date=due,
                      payment_method=data.payment_method, notes="Recorded for this month when added"),
            source="routine", extra={"occurrence_id": occ_id, "auto_deducted": auto})
        await db.planned_occurrences.update_one({"_id": occ_id}, {"$set": {"expense_id": parse_object_id(expense.id)}})
        out.this_month_expense_id = expense.id
    return out


async def list_routines(db, user_id) -> list[RoutineOut]:
    docs = await db.recurring_rules.find({"user_id": user_id}).sort("created_at", 1).to_list(None)
    return [RoutineOut(**to_out(d)) for d in docs]


async def get_routine(db, user_id, rule_id: str) -> RoutineOut:
    return RoutineOut(**to_out(await _get_rule(db, user_id, rule_id)))


async def update_routine(db, user_id, rule_id: str, data: RoutineIn) -> RoutineOut:
    existing = await _get_rule(db, user_id, rule_id)
    fields = _rule_doc(data)
    if data.start_date is None:  # keep the original start date when not provided
        fields["start_date"] = existing["start_date"]
    doc = await db.recurring_rules.find_one_and_update(
        {"_id": existing["_id"], "user_id": user_id},
        {"$set": {**fields, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    # Future, untouched occurrences are regenerated from the new schedule.
    # Rescheduled ones are kept but take the new name/amount/category.
    await _drop_future_planned(db, user_id, existing["_id"], keep_rescheduled=True)
    await db.planned_occurrences.update_many(
        {"user_id": user_id, "rule_id": existing["_id"], "status": "planned",
         "scheduled_date": {"$gte": date_str(dates.app_today())}},
        {"$set": {"name": doc["name"], "amount_paise": doc["amount_paise"], "category": doc["category"]}},
    )
    return RoutineOut(**to_out(doc))


async def set_active(db, user_id, rule_id: str, active: bool) -> RoutineOut:
    existing = await _get_rule(db, user_id, rule_id)
    doc = await db.recurring_rules.find_one_and_update(
        {"_id": existing["_id"], "user_id": user_id},
        {"$set": {"active": active, "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if not active:
        # Paused: future plans stop reserving money. They come back when resumed.
        await _drop_future_planned(db, user_id, existing["_id"], keep_rescheduled=False)
    return RoutineOut(**to_out(doc))


async def delete_routine(db, user_id, rule_id: str) -> None:
    existing = await _get_rule(db, user_id, rule_id)
    # Remove plans that never happened; keep spent/skipped history.
    await db.planned_occurrences.delete_many({"user_id": user_id, "rule_id": existing["_id"], "status": "planned"})
    await db.recurring_rules.delete_one({"_id": existing["_id"], "user_id": user_id})
