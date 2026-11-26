"""Actions on planned occurrences: mark spent, skip, restore, reschedule."""
from datetime import date, timedelta

from fastapi import HTTPException, status
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.schemas.expense import ExpenseIn
from app.schemas.routine import OccurrenceOut, RescheduleRequest, SpendRequest, SpendResult
from app.services import expense_service, routine_service
from app.services.budget_service import get_budget_doc
from app.utils import dates
from app.utils.ids import parse_object_id
from app.utils.periods import period_containing
from app.utils.serialize import date_str, to_out

MAX_RESCHEDULE_DAYS = 365


def _out(doc: dict) -> OccurrenceOut:
    return OccurrenceOut(**to_out(doc))


async def current_period(db, user_id):
    budget = await get_budget_doc(db, user_id)
    start_day = budget["period_start_day"] if budget else 1
    return period_containing(dates.app_today(), start_day)


async def list_occurrences(db, user_id, date_from: date | None, date_to: date | None,
                           status_filter: str | None = None) -> list[OccurrenceOut]:
    period = await current_period(db, user_id)
    date_from = date_from or period.start
    date_to = date_to or period.end
    if date_to < date_from:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "'to' must be on or after 'from'")
    if (date_to - date_from).days > routine_service.MAX_GENERATION_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Date range is too long (max ~3 months)")
    await routine_service.ensure_occurrences(db, user_id, date_from, date_to, earliest=period.start)
    f = {"user_id": user_id, "scheduled_date": {"$gte": date_str(date_from), "$lte": date_str(date_to)}}
    if status_filter:
        f["status"] = status_filter
    docs = await db.planned_occurrences.find(f).sort([("scheduled_date", ASCENDING), ("name", ASCENDING)]).to_list(None)
    modes = await routine_service.deduction_modes(db, user_id)
    return [_out({**d, "deduction_mode": modes.get(d["rule_id"], "manual")}) for d in docs]


async def _get(db, user_id, occurrence_id: str) -> dict:
    doc = await db.planned_occurrences.find_one(
        {"_id": parse_object_id(occurrence_id, "Planned expense"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Planned expense not found")
    return doc


async def mark_spent(db, user_id, occurrence_id: str, req: SpendRequest) -> SpendResult:
    occ = await _get(db, user_id, occurrence_id)
    if occ["status"] == "spent":
        raise HTTPException(status.HTTP_409_CONFLICT, "This planned expense is already marked as spent")
    if occ["status"] != "planned":
        raise HTTPException(status.HTTP_409_CONFLICT, "Restore this skipped expense before marking it spent")

    today = dates.app_today()
    scheduled = date.fromisoformat(occ["scheduled_date"])
    expense_in = ExpenseIn(
        amount_paise=req.amount_paise or occ["amount_paise"],
        category=occ["category"],
        description=occ["name"],
        date=req.date or min(scheduled, today),
        payment_method=req.payment_method or occ.get("payment_method", "upi"),
    )
    try:
        # The unique index on expenses.occurrence_id guarantees "exactly once",
        # even if the user double-taps or two requests race.
        expense = await expense_service.create_expense(
            db, user_id, expense_in, source="routine", extra={"occurrence_id": occ["_id"]})
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This planned expense is already marked as spent")
    doc = await db.planned_occurrences.find_one_and_update(
        {"_id": occ["_id"], "user_id": user_id},
        {"$set": {"status": "spent", "expense_id": parse_object_id(expense.id)}},
        return_document=ReturnDocument.AFTER,
    )
    return SpendResult(occurrence=_out(doc), expense_id=expense.id)


async def _transition(db, user_id, occurrence_id: str, from_status: str, update: dict, error: str) -> OccurrenceOut:
    occ = await _get(db, user_id, occurrence_id)
    doc = await db.planned_occurrences.find_one_and_update(
        {"_id": occ["_id"], "user_id": user_id, "status": from_status},
        {"$set": update},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, error)
    return _out(doc)


async def skip(db, user_id, occurrence_id: str) -> OccurrenceOut:
    # Skipping releases the reserved money: the engine only reserves status == "planned".
    return await _transition(db, user_id, occurrence_id, "planned", {"status": "skipped"},
                             "Only a planned expense can be skipped")


async def restore(db, user_id, occurrence_id: str) -> OccurrenceOut:
    return await _transition(db, user_id, occurrence_id, "skipped", {"status": "planned"},
                             "Only a skipped expense can be restored")


async def reschedule(db, user_id, occurrence_id: str, req: RescheduleRequest) -> OccurrenceOut:
    today = dates.app_today()
    if req.new_date < today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick today or a future date")
    if req.new_date > today + timedelta(days=MAX_RESCHEDULE_DAYS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a date within the next year")
    # Same document is updated (original_date is kept), so no duplicate is created.
    return await _transition(db, user_id, occurrence_id, "planned",
                             {"scheduled_date": date_str(req.new_date), "rescheduled": True},
                             "Only a planned expense can be rescheduled")
