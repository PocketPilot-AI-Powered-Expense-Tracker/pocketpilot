"""Pending (detected) UPI transactions and the review workflow.

    detected  ->  pending_review  --accept-->  accepted  (exactly one expense created)
                                  --reject-->  rejected  (nothing created)
    rejected  --restore-->  pending_review

Pending and rejected transactions are never expenses, so the budget engine never
sees them. Only `accept` creates an expense.

Duplicate prevention
  * transaction_ref  -> stored as SHA-256(user, ref) in a unique `dedupe_ref` field
  * notification_hash -> stored as "user:hash" in a unique `dedupe_hash` field
  * accept           -> client sends an Idempotency-Key; a retry with the same key
                        returns the original result. The expense has a unique
                        `pending_id`, so two expenses can never exist for one transaction.
Amount + date are NOT used, because two genuine payments can share them.
"""
import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import ValidationError
from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.schemas.expense import ExpenseIn
from app.schemas.pending import (AcceptRequest, AcceptResult, DetectedTransactionIn, PendingList, PendingOut,
                                 PendingSummary, SimulatedNotificationIn, SubmitResult)
from app.services import expense_service
from app.utils import dates
from app.utils.categorize import suggest_category
from app.utils.ids import parse_object_id
from app.utils.serialize import to_out
from app.utils.upi_parser import NotAPayment, parse_notification

APP_LABELS = {"phonepe": "PhonePe", "gpay": "Google Pay", "paytm": "Paytm", "bhim": "BHIM", "other": "UPI"}
_INTERNAL = ("dedupe_ref", "dedupe_hash", "idempotency_key")


def _out(doc: dict) -> PendingOut:
    d = to_out(doc)
    for k in _INTERNAL:
        d.pop(k, None)
    return PendingOut(**d)


def notification_hash(source_app: str, title: str, text: str, posted_at: datetime) -> str:
    raw = f"{source_app}|{title}|{text}|{posted_at.astimezone(timezone.utc).isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ref_key(user_id, ref: str) -> str:
    return hashlib.sha256(f"{user_id}:{ref.upper()}".encode()).hexdigest()


async def submit_detected(db, user_id, data: DetectedTransactionIn, *, origin: str = "detector") -> SubmitResult:
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "amount_paise": data.amount_paise,
        "source_app": data.source_app,
        "counterparty": data.counterparty,
        "ref_last4": data.transaction_ref[-4:] if data.transaction_ref else None,
        "detected_at": data.detected_at,
        "status": "pending_review",
        "suggested_category": suggest_category(data.counterparty),
        "origin": origin,
        "created_at": now,
    }
    # Only set dedupe fields when present (they use sparse unique indexes).
    if data.transaction_ref:
        doc["dedupe_ref"] = _ref_key(user_id, data.transaction_ref)
    if data.notification_hash:
        doc["dedupe_hash"] = f"{user_id}:{data.notification_hash}"
    try:
        result = await db.pending_transactions.insert_one(doc)
    except DuplicateKeyError:
        conditions = [{k: doc[k]} for k in ("dedupe_ref", "dedupe_hash") if k in doc]
        existing = await db.pending_transactions.find_one({"user_id": user_id, "$or": conditions})
        if existing is None:  # pragma: no cover - only if the duplicate was deleted meanwhile
            raise HTTPException(status.HTTP_409_CONFLICT, "Duplicate transaction")
        return SubmitResult(duplicate=True, transaction=_out(existing))
    doc["_id"] = result.inserted_id
    return SubmitResult(duplicate=False, transaction=_out(doc))


async def submit_simulated(db, user_id, data: SimulatedNotificationIn) -> SubmitResult:
    if not get_settings().ENABLE_NOTIFICATION_SIMULATOR:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Simulator is disabled")
    try:
        parsed = parse_notification(data.title, data.text)
    except NotAPayment as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    posted_at = data.posted_at or dates.utc_now()
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    try:
        detected = DetectedTransactionIn(
            amount_paise=parsed.amount_paise,
            source_app=data.source_app,
            counterparty=parsed.counterparty,
            transaction_ref=parsed.transaction_ref,
            notification_hash=notification_hash(data.source_app, data.title, data.text, posted_at),
            detected_at=posted_at,
        )
    except ValidationError as e:
        msg = e.errors()[0]["msg"].removeprefix("Value error, ")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, msg)
    return await submit_detected(db, user_id, detected, origin="simulator")


async def list_pending(db, user_id, status_filter: str | None) -> PendingList:
    f = {"user_id": user_id}
    if status_filter:
        f["status"] = status_filter
    docs = await db.pending_transactions.find(f).sort("detected_at", DESCENDING).limit(200).to_list(None)
    counts = {"pending_review": 0, "accepted": 0, "rejected": 0}
    for s in counts:
        counts[s] = await db.pending_transactions.count_documents({"user_id": user_id, "status": s})
    return PendingList(items=[_out(d) for d in docs], counts=counts)


async def summary(db, user_id) -> PendingSummary:
    docs = await db.pending_transactions.find({"user_id": user_id, "status": "pending_review"},
                                              {"amount_paise": 1}).to_list(None)
    return PendingSummary(pending_count=len(docs), pending_total_paise=sum(d["amount_paise"] for d in docs))


async def _get(db, user_id, pending_id: str) -> dict:
    doc = await db.pending_transactions.find_one({"_id": parse_object_id(pending_id, "Transaction"), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return doc


def _local_date(dt_value: datetime):
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(ZoneInfo(get_settings().APP_TIMEZONE)).date()


async def _create_linked_expense(db, user_id, pending: dict, expense_in: ExpenseIn) -> str:
    try:
        exp = await expense_service.create_expense(db, user_id, expense_in, source="upi_review",
                                                   extra={"pending_id": pending["_id"]})
        return exp.id
    except DuplicateKeyError:
        existing = await db.expenses.find_one({"pending_id": pending["_id"], "user_id": user_id})
        return str(existing["_id"])


async def accept(db, user_id, pending_id: str, req: AcceptRequest, idempotency_key: str | None) -> AcceptResult:
    pending = await _get(db, user_id, pending_id)

    # Idempotent replay: same key as the request that already accepted it.
    if pending["status"] == "accepted":
        if idempotency_key and pending.get("idempotency_key") == idempotency_key:
            expense_id = pending.get("expense_id")
            if expense_id is None:  # previous attempt stopped half-way: finish it
                raise HTTPException(status.HTTP_409_CONFLICT, "Accept is still in progress, try again")
            return AcceptResult(transaction=_out(pending), expense_id=str(expense_id), replayed=True)
        raise HTTPException(status.HTTP_409_CONFLICT, "This transaction was already added to your expenses")
    if pending["status"] == "rejected":
        raise HTTPException(status.HTTP_409_CONFLICT, "This transaction was rejected. Restore it first to add it.")

    # Validate the final expense BEFORE changing anything.
    description = req.description or pending.get("counterparty") or f"{APP_LABELS[pending['source_app']]} payment"
    try:
        expense_in = ExpenseIn(
            amount_paise=req.amount_paise or pending["amount_paise"],
            category=req.category or pending["suggested_category"],
            description=description,
            date=req.date or min(_local_date(pending["detected_at"]), dates.app_today()),
            payment_method=req.payment_method or "upi",
            notes=req.notes,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e).split("\n")[-1].strip())

    # Atomically claim it: only one request can move pending_review -> accepted,
    # so a concurrent reject or second accept cannot also win.
    claimed = await db.pending_transactions.find_one_and_update(
        {"_id": pending["_id"], "user_id": user_id, "status": "pending_review"},
        {"$set": {"status": "accepted", "idempotency_key": idempotency_key, "reviewed_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if claimed is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This transaction was already reviewed")
    try:
        expense_id = await _create_linked_expense(db, user_id, claimed, expense_in)
    except Exception:
        # Roll the claim back so the user can try again.
        await db.pending_transactions.update_one(
            {"_id": claimed["_id"]}, {"$set": {"status": "pending_review"}, "$unset": {"idempotency_key": "", "reviewed_at": ""}})
        raise
    doc = await db.pending_transactions.find_one_and_update(
        {"_id": claimed["_id"]}, {"$set": {"expense_id": parse_object_id(expense_id)}},
        return_document=ReturnDocument.AFTER,
    )
    return AcceptResult(transaction=_out(doc), expense_id=expense_id)


async def reject(db, user_id, pending_id: str) -> PendingOut:
    pending = await _get(db, user_id, pending_id)
    doc = await db.pending_transactions.find_one_and_update(
        {"_id": pending["_id"], "user_id": user_id, "status": "pending_review"},
        {"$set": {"status": "rejected", "reviewed_at": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a transaction awaiting review can be rejected")
    return _out(doc)


async def restore(db, user_id, pending_id: str) -> PendingOut:
    pending = await _get(db, user_id, pending_id)
    doc = await db.pending_transactions.find_one_and_update(
        {"_id": pending["_id"], "user_id": user_id, "status": "rejected"},
        {"$set": {"status": "pending_review"}, "$unset": {"reviewed_at": ""}},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a rejected transaction can be restored")
    return _out(doc)
