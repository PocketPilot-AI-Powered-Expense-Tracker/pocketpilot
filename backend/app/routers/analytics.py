from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.db.mongo import get_db
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard(user=Depends(get_current_user), db=Depends(get_db)):
    return await analytics_service.dashboard(db, user["_id"])


@router.get("/safe-to-spend")
async def safe_to_spend(user=Depends(get_current_user), db=Depends(get_db)):
    return await analytics_service.safe_to_spend(db, user["_id"])


@router.get("/categories")
async def categories(offset: int = Query(0, ge=0, le=24, description="0 = current period, 1 = previous…"),
                     user=Depends(get_current_user), db=Depends(get_db)):
    return await analytics_service.category_breakdown(db, user["_id"], offset)


@router.get("/monthly-comparison")
async def monthly_comparison(months: int = Query(6, ge=2, le=12), user=Depends(get_current_user), db=Depends(get_db)):
    return await analytics_service.monthly_comparison(db, user["_id"], months)
