import datetime as dt

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.schemas.routine import (OccurrenceOut, OccurrenceStatus, RescheduleRequest, RoutineIn, RoutineOut,
                                 SpendRequest, SpendResult)
from app.services import occurrence_service, routine_service

router = APIRouter(prefix="/api/routines", tags=["recurring routines"])
occ_router = APIRouter(prefix="/api/occurrences", tags=["planned occurrences"])


@router.post("", response_model=RoutineOut, status_code=status.HTTP_201_CREATED)
async def create(data: RoutineIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.create_routine(db, user["_id"], data)


@router.get("", response_model=list[RoutineOut])
async def list_(user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.list_routines(db, user["_id"])


@router.get("/{rule_id}", response_model=RoutineOut)
async def get(rule_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.get_routine(db, user["_id"], rule_id)


@router.put("/{rule_id}", response_model=RoutineOut)
async def update(rule_id: str, data: RoutineIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.update_routine(db, user["_id"], rule_id, data)


@router.post("/{rule_id}/pause", response_model=RoutineOut)
async def pause(rule_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.set_active(db, user["_id"], rule_id, False)


@router.post("/{rule_id}/resume", response_model=RoutineOut)
async def resume(rule_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await routine_service.set_active(db, user["_id"], rule_id, True)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(rule_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    await routine_service.delete_routine(db, user["_id"], rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@occ_router.get("", response_model=list[OccurrenceOut])
async def list_occurrences(
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    status_filter: OccurrenceStatus | None = Query(None, alias="status"),
    user=Depends(get_current_user), db=Depends(get_db),
):
    return await occurrence_service.list_occurrences(db, user["_id"], date_from, date_to, status_filter)


@occ_router.post("/{occurrence_id}/spend", response_model=SpendResult)
async def spend(occurrence_id: str, req: SpendRequest | None = None, user=Depends(get_current_user), db=Depends(get_db)):
    return await occurrence_service.mark_spent(db, user["_id"], occurrence_id, req or SpendRequest())


@occ_router.post("/{occurrence_id}/skip", response_model=OccurrenceOut)
async def skip(occurrence_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await occurrence_service.skip(db, user["_id"], occurrence_id)


@occ_router.post("/{occurrence_id}/restore", response_model=OccurrenceOut)
async def restore(occurrence_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await occurrence_service.restore(db, user["_id"], occurrence_id)


@occ_router.post("/{occurrence_id}/reschedule", response_model=OccurrenceOut)
async def reschedule(occurrence_id: str, req: RescheduleRequest, user=Depends(get_current_user), db=Depends(get_db)):
    return await occurrence_service.reschedule(db, user["_id"], occurrence_id, req)
