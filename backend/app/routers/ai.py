from fastapi import APIRouter, Depends, Query

from app.ai.provider import get_ai_provider
from app.core.deps import get_current_user
from app.core.rate_limit import ai_rate_limit
from app.db.mongo import get_db
from app.schemas.ai import AskRequest, AskResponse, InsightsResponse, ProposalOut, ProposeRequest
from app.services import ai_actions, ai_assistant, ai_insights

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
async def ai_status(user=Depends(get_current_user), ai=Depends(get_ai_provider)):
    return {"ai_available": ai is not None, "provider": getattr(ai, "name", None)}


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest, user=Depends(ai_rate_limit), db=Depends(get_db), ai=Depends(get_ai_provider)):
    return await ai_assistant.ask(db, user["_id"], req.question, ai)


@router.post("/actions/propose", response_model=ProposalOut,
             summary="Interpret a natural-language request into a proposal. Changes nothing.")
async def propose(req: ProposeRequest, user=Depends(ai_rate_limit), db=Depends(get_db), ai=Depends(get_ai_provider)):
    return await ai_actions.propose(db, user["_id"], req.text, ai)


@router.post("/actions/{proposal_id}/confirm", response_model=ProposalOut,
             summary="Execute a proposal after the user confirms it (at most once).")
async def confirm(proposal_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await ai_actions.confirm(db, user["_id"], proposal_id)


@router.post("/actions/{proposal_id}/cancel", response_model=ProposalOut)
async def cancel(proposal_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    return await ai_actions.cancel(db, user["_id"], proposal_id)


@router.get("/insights", response_model=InsightsResponse)
async def insights(user=Depends(ai_rate_limit), db=Depends(get_db), ai=Depends(get_ai_provider)):
    return await ai_insights.insights(db, user["_id"], ai)


@router.get("/report")
async def report(offset: int = Query(0, ge=0, le=12, description="0 = this month, 1 = last month…"),
                 user=Depends(ai_rate_limit), db=Depends(get_db), ai=Depends(get_ai_provider)):
    return await ai_insights.report(db, user["_id"], offset, ai)
