import re
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from pymongo import DESCENDING

from app.schemas.expense import ExpenseIn, ExpenseList, ExpenseOut
from app.utils.ids import parse_object_id
from app.utils.serialize import date_str, to_out


def _doc_from_input(data: ExpenseIn) -> dict:
    d = data.model_dump()
    d["date"] = date_str(data.date)
    return d


def build_filter(user_id, date_from: date | None = None, date_to: date | None = None,
                 category: str | None = None, q: str | None = None) -> dict:
    f: dict = {"user_id": user_id}
    if date_from or date_to:
        f["date"] = {}
        if date_from:
            f["date"]["$gte"] = date_str(date_from)
        if date_to:
            f["date"]["$lte"] = date_str(date_to)
    if category:
        f["category"] = category
    if q and q.strip():
        pattern = re.escape(q.strip()[:60])
        f["$or"] = [{"description": {"$regex": pattern, "$options": "i"}},
                    {"notes": {"$regex": pattern, "$options": "i"}}]
    return f


async def create_expense(db, user_id, data: ExpenseIn, *, source: str = "manual", extra: dict | None = None) -> ExpenseOut:
    """`extra` lets other services link the expense (e.g. occurrence_id). Linked fields
    are unique-indexed, so the same occurrence can never produce two expenses."""
    now = datetime.now(timezone.utc)
    doc = {"user_id": user_id, **_doc_from_input(data), "source": source, **(extra or {}),
           "created_at": now, "updated_at": now}
    result = await db.expenses.insert_one(doc)
    doc["_id"] = result.inserted_id
    return ExpenseOut(**to_out(doc))


async def list_expenses(db, user_id, *, limit: int = 50, skip: int = 0, **filters) -> ExpenseList:
    from app.services.routine_service import sync_current_period

    await sync_current_period(db, user_id)  # so automatic deductions show up here too
    f = build_filter(user_id, **filters)
    docs = await db.expenses.find(f).sort([("date", DESCENDING), ("created_at", DESCENDING)]).skip(skip).limit(limit).to_list(None)
    total = await db.expenses.count_documents(f)
    amount = sum(d["amount_paise"] for d in await db.expenses.find(f, {"amount_paise": 1}).to_list(None))
    return ExpenseList(items=[ExpenseOut(**to_out(d)) for d in docs], total=total, total_amount_paise=amount)


async def get_expense(db, user_id, expense_id: str) -> ExpenseOut:
    doc = await db.expenses.find_one({"_id": parse_object_id(expense_id, "Expense"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return ExpenseOut(**to_out(doc))


async def update_expense(db, user_id, expense_id: str, data: ExpenseIn) -> ExpenseOut:
    from pymongo import ReturnDocument

    doc = await db.expenses.find_one_and_update(
        {"_id": parse_object_id(expense_id, "Expense"), "user_id": user_id},
        {"$set": {**_doc_from_input(data), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return ExpenseOut(**to_out(doc))


async def delete_expense(db, user_id, expense_id: str) -> None:
    doc = await db.expenses.find_one_and_delete({"_id": parse_object_id(expense_id, "Expense"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    # If this expense came from a planned occurrence, put the occurrence back to "planned"
    # so it reserves money again (the money was not actually spent after all).
    if doc.get("occurrence_id"):
        if doc.get("auto_deducted"):
            # Deleting an automatic deduction means "this didn't happen": skip that date so it
            # isn't deducted again. (The user can Restore it on the Planned page.)
            await db.planned_occurrences.update_one(
                {"_id": doc["occurrence_id"], "user_id": user_id, "status": "spent"},
                {"$set": {"status": "skipped"}, "$unset": {"expense_id": "", "auto_deducted": ""}},
            )
        else:
            await db.planned_occurrences.update_one(
                {"_id": doc["occurrence_id"], "user_id": user_id, "status": "spent"},
                {"$set": {"status": "planned"}, "$unset": {"expense_id": ""}},
            )
    # If it came from a reviewed UPI transaction, send that back to "awaiting review"
    # so it is not lost (the user can then reject it if it wasn't personal spending).
    if doc.get("pending_id"):
        await db.pending_transactions.update_one(
            {"_id": doc["pending_id"], "user_id": user_id, "status": "accepted"},
            {"$set": {"status": "pending_review"}, "$unset": {"expense_id": "", "idempotency_key": "", "reviewed_at": ""}},
        )
