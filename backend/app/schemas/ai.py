import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Category

ToolName = Literal["safe_to_spend", "category_spending", "affordability", "spending_change",
                   "savings_plan", "top_category", "end_of_month", "overview"]


# ---- Shapes the AI must return (structured output) ----

class RoutePlan(BaseModel):
    tool: ToolName
    category: Category | None = None
    amount_rupees: float | None = Field(default=None, ge=0)


class ActionAI(BaseModel):
    action: Literal["add_expense", "add_income", "update_routine_amount", "skip_occurrence", "unsupported"]
    amount_rupees: float | None = None
    category: Category | None = None
    description: str | None = None
    date: str | None = None
    source: str | None = None
    counts_as_planned: bool | None = None
    routine_id: str | None = None
    occurrence_id: str | None = None
    reason: str | None = None


class InsightTip(BaseModel):
    id: str
    tip: str


class InsightTips(BaseModel):
    tips: list[InsightTip]


class ReportText(BaseModel):
    headline: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)


# ---- API request / response models ----

class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=300)


class FactOut(BaseModel):
    label: str
    value: str
    paise: int | None = None


class AskResponse(BaseModel):
    question: str
    tool: ToolName
    answer: str
    facts: list[FactOut]
    verdict: str | None = None
    answered_by: Literal["ai", "rules"]
    notice: str | None = None


class ProposeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=2, max_length=300)


class SummaryLine(BaseModel):
    label: str
    value: str


class ProposalOut(BaseModel):
    id: str | None = None
    status: Literal["proposed", "executed", "cancelled", "unsupported"]
    action: str
    title: str
    lines: list[SummaryLine] = Field(default_factory=list)
    message: str | None = None
    expires_at: dt.datetime | None = None
    interpreted_by: Literal["ai", "rules"]
    result: dict | None = None


class InsightOut(BaseModel):
    id: str
    kind: str
    severity: Literal["positive", "info", "warning"]
    title: str
    fact: str
    tip: str
    tip_by: Literal["ai", "rules"]


class InsightsResponse(BaseModel):
    insights: list[InsightOut]
    ai_available: bool
