import datetime as dt

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.schemas.income import IncomeIn, IncomeList, IncomeOut
from app.services import income_service

router = APIRouter(prefix="/api/income", tags=["income"])


@router.post("", response_model=IncomeOut, status_code=status.HTTP_201_CREATED)
async def create(data: IncomeIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await income_service.create_income(db, user["_id"], data)


@router.get("", response_model=IncomeList)
async def list_(
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    q: str | None = Query(None, max_length=60),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user=Depends(get_current_user), db=Depends(get_db),
):
    return await income_service.list_income(db, user["_id"], limit=limit, skip=skip,
                                            date_from=date_from, date_to=date_to, q=q)


@router.get("/{income_id}", response_model=IncomeOut)
async def get(income_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await income_service.get_income(db, user["_id"], income_id)


@router.put("/{income_id}", response_model=IncomeOut)
async def update(income_id: str, data: IncomeIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await income_service.update_income(db, user["_id"], income_id, data)


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(income_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    await income_service.delete_income(db, user["_id"], income_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
