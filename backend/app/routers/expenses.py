import datetime as dt

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.schemas.common import Category
from app.schemas.expense import ExpenseIn, ExpenseList, ExpenseOut
from app.services import expense_service

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create(data: ExpenseIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await expense_service.create_expense(db, user["_id"], data)


@router.get("", response_model=ExpenseList)
async def list_(
    date_from: dt.date | None = Query(None, alias="from"),
    date_to: dt.date | None = Query(None, alias="to"),
    category: Category | None = None,
    q: str | None = Query(None, max_length=60),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    user=Depends(get_current_user), db=Depends(get_db),
):
    return await expense_service.list_expenses(db, user["_id"], limit=limit, skip=skip,
                                               date_from=date_from, date_to=date_to, category=category, q=q)


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get(expense_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await expense_service.get_expense(db, user["_id"], expense_id)


@router.put("/{expense_id}", response_model=ExpenseOut)
async def update(expense_id: str, data: ExpenseIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await expense_service.update_expense(db, user["_id"], expense_id, data)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(expense_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    await expense_service.delete_expense(db, user["_id"], expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
