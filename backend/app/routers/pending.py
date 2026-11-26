from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.schemas.pending import (AcceptRequest, AcceptResult, DetectedTransactionIn, PendingList, PendingOut,
                                 PendingSummary, SimulatedNotificationIn, SubmitResult)
from app.services import pending_service

router = APIRouter(prefix="/api/pending-transactions", tags=["pending transactions"])


def _submit_response(result: SubmitResult, response: Response) -> SubmitResult:
    # 201 for a new record, 200 when it was a duplicate of an existing one.
    response.status_code = status.HTTP_200_OK if result.duplicate else status.HTTP_201_CREATED
    return result


@router.post("", response_model=SubmitResult, status_code=status.HTTP_201_CREATED,
             summary="Submit a detected transaction (used by the Android companion app)")
async def submit(data: DetectedTransactionIn, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return _submit_response(await pending_service.submit_detected(db, user["_id"], data), response)


@router.post("/simulate", response_model=SubmitResult, status_code=status.HTTP_201_CREATED,
             summary="Parse a sample notification and submit it (testing only)")
async def simulate(data: SimulatedNotificationIn, response: Response, user=Depends(get_current_user), db=Depends(get_db)):
    return _submit_response(await pending_service.submit_simulated(db, user["_id"], data), response)


@router.get("", response_model=PendingList)
async def list_(status_filter: Literal["pending_review", "accepted", "rejected", "all"] = Query("pending_review", alias="status"),
                user=Depends(get_current_user), db=Depends(get_db)):
    return await pending_service.list_pending(db, user["_id"], None if status_filter == "all" else status_filter)


@router.get("/summary", response_model=PendingSummary)
async def summary(user=Depends(get_current_user), db=Depends(get_db)):
    return await pending_service.summary(db, user["_id"])


@router.post("/{pending_id}/accept", response_model=AcceptResult,
             summary="Add to expenses. Send overrides in the body to 'Edit and add'.")
async def accept(pending_id: str, req: AcceptRequest | None = None,
                 idempotency_key: str | None = Header(None, alias="Idempotency-Key", max_length=100),
                 user=Depends(get_current_user), db=Depends(get_db)):
    return await pending_service.accept(db, user["_id"], pending_id, req or AcceptRequest(), idempotency_key)


@router.post("/{pending_id}/reject", response_model=PendingOut)
async def reject(pending_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await pending_service.reject(db, user["_id"], pending_id)


@router.post("/{pending_id}/restore", response_model=PendingOut, summary="Undo a rejection")
async def restore(pending_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await pending_service.restore(db, user["_id"], pending_id)
