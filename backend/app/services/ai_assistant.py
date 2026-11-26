"""'Ask PocketPilot': AI routes the question, Python calculates, AI explains, a guard checks."""
import json
import logging
import re

from app.ai import prompts
from app.ai.guard import clean_text, only_known_amounts, unknown_amounts
from app.ai.provider import AIProvider, AIUnavailable
from app.schemas.ai import AskResponse, FactOut, RoutePlan
from app.services import assistant_tools as tools
from app.services import finance_context
from app.utils.categorize import suggest_category

log = logging.getLogger(__name__)

_CATEGORY_WORDS = {
    "food": r"food|eat|lunch|dinner|breakfast|snack|tea|coffee|canteen|swiggy|zomato",
    "rent": r"rent|pg|hostel fees?|room|landlord|housing",
    "transportation": r"transport|travel|auto|bus|metro|uber|ola|cab|petrol|commute",
    "shopping": r"shopping|clothes|shop|amazon|flipkart",
    "entertainment": r"entertainment|movie|movies|games|concert|outing",
    "education": r"education|books?|stationery|course|college fees",
    "subscriptions": r"subscriptions?|netflix|spotify|recharge",
    "personal_care": r"personal care|salon|medicine|gym|haircut",
}
_AMOUNT = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(?:rupees|rs)?", re.I)


def _rupees_to_paise(value: float | None) -> int | None:
    if value is None or value <= 0:
        return None
    return int(round(value * 100))


def rule_route(question: str) -> RoutePlan:
    """Keyword router used when AI is unavailable."""
    q = question.lower()
    amount = None
    m = re.search(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d{1,2})?)|(\d[\d,]*(?:\.\d{1,2})?)\s*(?:rupees|rs\b)", q)
    if m:
        amount = float((m.group(1) or m.group(2)).replace(",", ""))
    if re.search(r"afford|can i buy|should i buy|purchase", q):
        if amount is None:
            m2 = _AMOUNT.search(q)
            amount = float(m2.group(1).replace(",", "")) if m2 else None
        return RoutePlan(tool="affordability", amount_rupees=amount)
    category = next((c for c, pat in _CATEGORY_WORDS.items() if re.search(rf"\b(?:{pat})\b", q)), None)
    if category and re.search(r"spen[dt]|cost|how much", q):
        return RoutePlan(tool="category_spending", category=category)
    if re.search(r"\bwhy\b|more than (?:usual|last)|increase|compared", q):
        return RoutePlan(tool="spending_change")
    if re.search(r"biggest|highest|most|largest|top", q):
        return RoutePlan(tool="top_category")
    if re.search(r"\bsav(?:e|ing|ings)\b", q):
        return RoutePlan(tool="savings_plan")
    if re.search(r"left|end of (?:the )?month|remain", q):
        return RoutePlan(tool="end_of_month")
    if re.search(r"today|spend|daily", q):
        return RoutePlan(tool="safe_to_spend")
    return RoutePlan(tool="overview")


async def ask(db, user_id, question: str, ai: AIProvider | None) -> AskResponse:
    ctx = await finance_context.load(db, user_id)
    notice = None
    routed_by_ai = False

    plan = None
    if ai:
        try:
            plan = await ai.generate_json(system=prompts.ROUTER, prompt=f"QUESTION: {question}", schema=RoutePlan)
            routed_by_ai = True
        except AIUnavailable as e:
            log.warning("AI routing failed: %s", e)
    if plan is None:
        plan = rule_route(question)
    if plan.tool == "category_spending" and not plan.category:
        plan.category = suggest_category(question) if suggest_category(question) != "other" else None

    result = tools.run_tool(ctx, plan.tool, category=plan.category, amount_paise=_rupees_to_paise(plan.amount_rupees))
    facts = [f.to_dict() for f in result.facts]

    answer, answered_by = result.answer, "rules"
    if ai and routed_by_ai:
        # Only aggregated, verified numbers are sent — no names, emails, merchants or notes.
        prompt = json.dumps({"QUESTION": question, "FACTS": {f["label"]: f["value"] for f in facts},
                             "VERDICT": result.verdict, "REFERENCE_ANSWER": result.answer}, ensure_ascii=False)
        try:
            text = clean_text(await ai.generate_text(system=prompts.EXPLAIN, prompt=prompt))
            if only_known_amounts(text, result.allowed_paise):
                answer, answered_by = text, "ai"
            else:
                notice = "The AI's wording mentioned an amount we couldn't verify, so a calculated answer is shown instead."
                log.warning("AI answer failed number guard (unverified amounts in paise: %s)",
                            unknown_amounts(text, result.allowed_paise)[:5])
        except AIUnavailable as e:
            log.warning("AI explanation failed: %s", e)
    if not ai:
        notice = "AI is not configured, so this is PocketPilot's built-in answer."
    elif answered_by == "rules" and notice is None:
        notice = "The AI service didn't respond, so this is PocketPilot's built-in answer."

    return AskResponse(question=question, tool=plan.tool, answer=answer, facts=[FactOut(**f) for f in facts],
                       verdict=result.verdict, answered_by=answered_by, notice=notice)
