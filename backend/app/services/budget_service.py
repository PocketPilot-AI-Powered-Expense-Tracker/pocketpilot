from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.schemas.budget import BudgetIn, BudgetOut, PeriodOut
from app.utils import dates
from app.utils.periods import Period, period_containing
from app.utils.serialize import date_str

OPENING_DESCRIPTION = "Spent earlier this month"
OPENING_NOTES = "Entered on the Budget page (money spent before today)"


def _opening_filter(user_id, period: Period) -> dict:
    return {"user_id": user_id, "source": "opening", "period_start": date_str(period.start)}


async def _opening_amount(db, user_id, period: Period) -> int:
    doc = await db.expenses.find_one(_opening_filter(user_id, period), {"amount_paise": 1})
    return doc["amount_paise"] if doc else 0


def _check_opening_allowed(data: BudgetIn, today: date) -> None:
    if data.spent_before_today_paise:
        period = period_containing(today, data.period_start_day)
        if today <= period.start:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "Your budget month starts today, so nothing was spent before today yet.")


async def _save_opening(db, user_id, data: BudgetIn, today: date) -> None:
    """Keep one 'spent earlier this month' expense per budget period.
    It is dated yesterday, so it lowers what's left but not today's safe-to-spend."""
    amount = data.spent_before_today_paise
    if amount is None:
        return
    period = period_containing(today, data.period_start_day)
    key = _opening_filter(user_id, period)
    now = datetime.now(timezone.utc)
    if amount == 0:
        await db.expenses.delete_one(key)
        return
    if await db.expenses.find_one(key):
        await db.expenses.update_one(key, {"$set": {"amount_paise": amount, "updated_at": now}})
        return
    await db.expenses.insert_one({
        **key,
        "amount_paise": amount,
        "category": "other",
        "description": OPENING_DESCRIPTION,
        "date": date_str(today - timedelta(days=1)),
        "payment_method": "other",
        "notes": OPENING_NOTES,
        "created_at": now,
        "updated_at": now,
    })


def to_budget_out(doc: dict, today: date | None = None, spent_before_today: int = 0) -> BudgetOut:
    today = today or dates.app_today()
    period = period_containing(today, doc["period_start_day"])
    planned_income = doc["monthly_allowance_paise"] + doc["additional_income_paise"]
    return BudgetOut(
        id=str(doc["_id"]),
        monthly_allowance_paise=doc["monthly_allowance_paise"],
        additional_income_paise=doc["additional_income_paise"],
        savings_target_paise=doc["savings_target_paise"],
        period_start_day=doc["period_start_day"],
        spent_before_today_paise=spent_before_today,
        planned_income_paise=planned_income,
        planned_spendable_paise=planned_income - doc["savings_target_paise"],
        current_period=PeriodOut(
            start=period.start,
            end=period.end,
            total_days=period.total_days,
            days_remaining=period.days_remaining(today),
        ),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


async def _out(db, user_id, doc: dict) -> BudgetOut:
    today = dates.app_today()
    period = period_containing(today, doc["period_start_day"])
    return to_budget_out(doc, today, await _opening_amount(db, user_id, period))


async def get_budget_doc(db, user_id) -> dict | None:
    return await db.budgets.find_one({"user_id": user_id})


async def create_budget(db, user_id, data: BudgetIn) -> BudgetOut:
    today = dates.app_today()
    _check_opening_allowed(data, today)
    now = datetime.now(timezone.utc)
    doc = {"user_id": user_id, **data.model_dump(exclude={"spent_before_today_paise"}),
           "created_at": now, "updated_at": now}
    try:
        result = await db.budgets.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Budget already exists. Update it instead.")
    doc["_id"] = result.inserted_id
    await _save_opening(db, user_id, data, today)
    return await _out(db, user_id, doc)


async def get_budget(db, user_id) -> BudgetOut:
    doc = await get_budget_doc(db, user_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No budget set up yet")
    return await _out(db, user_id, doc)


async def update_budget(db, user_id, data: BudgetIn) -> BudgetOut:
    today = dates.app_today()
    _check_opening_allowed(data, today)
    doc = await db.budgets.find_one_and_update(
        {"user_id": user_id},
        {"$set": {**data.model_dump(exclude={"spent_before_today_paise"}), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No budget set up yet")
    await _save_opening(db, user_id, data, today)
    return await _out(db, user_id, doc)
