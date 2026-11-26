from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.schemas.budget import BudgetIn, BudgetOut
from app.services import budget_service

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(data: BudgetIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await budget_service.create_budget(db, user["_id"], data)


@router.get("", response_model=BudgetOut)
async def get_budget(user=Depends(get_current_user), db=Depends(get_db)):
    return await budget_service.get_budget(db, user["_id"])


@router.put("", response_model=BudgetOut)
async def update_budget(data: BudgetIn, user=Depends(get_current_user), db=Depends(get_db)):
    return await budget_service.update_budget(db, user["_id"], data)
