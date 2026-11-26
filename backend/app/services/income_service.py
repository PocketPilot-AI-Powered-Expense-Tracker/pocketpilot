import re
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from pymongo import DESCENDING, ReturnDocument

from app.schemas.income import IncomeIn, IncomeList, IncomeOut
from app.utils.ids import parse_object_id
from app.utils.serialize import date_str, to_out


def _doc_from_input(data: IncomeIn) -> dict:
    d = data.model_dump()
    d["date"] = date_str(data.date)
    return d


def build_filter(user_id, date_from: date | None = None, date_to: date | None = None, q: str | None = None) -> dict:
    f: dict = {"user_id": user_id}
    if date_from or date_to:
        f["date"] = {}
        if date_from:
            f["date"]["$gte"] = date_str(date_from)
        if date_to:
            f["date"]["$lte"] = date_str(date_to)
    if q and q.strip():
        pattern = re.escape(q.strip()[:60])
        f["$or"] = [{"source": {"$regex": pattern, "$options": "i"}},
                    {"description": {"$regex": pattern, "$options": "i"}}]
    return f


async def create_income(db, user_id, data: IncomeIn) -> IncomeOut:
    now = datetime.now(timezone.utc)
    doc = {"user_id": user_id, **_doc_from_input(data), "created_at": now, "updated_at": now}
    result = await db.income.insert_one(doc)
    doc["_id"] = result.inserted_id
    return IncomeOut(**to_out(doc))


async def list_income(db, user_id, *, limit: int = 50, skip: int = 0, **filters) -> IncomeList:
    f = build_filter(user_id, **filters)
    docs = await db.income.find(f).sort([("date", DESCENDING), ("created_at", DESCENDING)]).skip(skip).limit(limit).to_list(None)
    total = await db.income.count_documents(f)
    amount = sum(d["amount_paise"] for d in await db.income.find(f, {"amount_paise": 1}).to_list(None))
    return IncomeList(items=[IncomeOut(**to_out(d)) for d in docs], total=total, total_amount_paise=amount)


async def get_income(db, user_id, income_id: str) -> IncomeOut:
    doc = await db.income.find_one({"_id": parse_object_id(income_id, "Income"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Income not found")
    return IncomeOut(**to_out(doc))


async def update_income(db, user_id, income_id: str, data: IncomeIn) -> IncomeOut:
    doc = await db.income.find_one_and_update(
        {"_id": parse_object_id(income_id, "Income"), "user_id": user_id},
        {"$set": {**_doc_from_input(data), "updated_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Income not found")
    return IncomeOut(**to_out(doc))


async def delete_income(db, user_id, income_id: str) -> None:
    result = await db.income.delete_one({"_id": parse_object_id(income_id, "Income"), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Income not found")
