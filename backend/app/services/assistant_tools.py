"""Deterministic "tools" that answer money questions. The AI only chooses which tool
to run and explains the result; every number here is calculated in Python."""
from collections import defaultdict
from dataclasses import dataclass, field

from app.services.finance_context import FinanceContext
from app.utils.money import format_inr

CATEGORY_LABELS = {
    "food": "Food", "rent": "Rent", "transportation": "Transportation", "shopping": "Shopping", "entertainment": "Entertainment",
    "education": "Education", "subscriptions": "Subscriptions", "personal_care": "Personal care", "other": "Other",
}
TOOL_NAMES = ("safe_to_spend", "category_spending", "affordability", "spending_change",
              "savings_plan", "top_category", "end_of_month", "overview")


@dataclass
class Fact:
    label: str
    paise: int | None = None
    text: str | None = None

    @property
    def display(self) -> str:
        return format_inr(self.paise) if self.paise is not None else (self.text or "")

    def to_dict(self) -> dict:
        return {"label": self.label, "value": self.display, "paise": self.paise}


@dataclass
class ToolResult:
    tool: str
    facts: list[Fact]
    answer: str  # deterministic plain-language answer (used when AI is off or fails the guard)
    verdict: str | None = None
    extra_allowed: set[int] = field(default_factory=set)

    @property
    def allowed_paise(self) -> set[int]:
        return {f.paise for f in self.facts if f.paise is not None} | self.extra_allowed


def _days(n: int) -> str:
    return f"{n} day{'s' if n != 1 else ''}"


def safe_to_spend(ctx: FinanceContext) -> ToolResult:
    s = ctx.summary
    facts = [
        Fact("Safe to spend today", s.safe_to_spend_today_paise),
        Fact("Daily budget", s.daily_recommendation_paise),
        Fact("Unplanned spending today", s.spent_today_unplanned_paise),
        Fact("Free to spend this month", max(0, s.free_to_spend_paise)),
        Fact("Days left", text=str(s.days_remaining)),
    ]
    answer = (f"You can safely spend {format_inr(s.safe_to_spend_today_paise)} today. Your daily budget is "
              f"{format_inr(s.daily_recommendation_paise)} for the {_days(s.days_remaining)} left, and you've spent "
              f"{format_inr(s.spent_today_unplanned_paise)} on unplanned things today.")
    return ToolResult("safe_to_spend", facts, answer)


def category_spending(ctx: FinanceContext, category: str | None) -> ToolResult:
    if not category or category not in CATEGORY_LABELS:
        return overview(ctx)
    label = CATEGORY_LABELS[category]
    items = [e for e in ctx.expenses if e.category == category]
    total = sum(e.amount_paise for e in items)
    prev = sum(e.amount_paise for e in ctx.prev_same_point() if e.category == category)
    facts = [Fact(f"{label} spending this month", total), Fact("Number of expenses", text=str(len(items))),
             Fact(f"{label} by this point last month", prev)]
    answer = f"You've spent {format_inr(total)} on {label.lower()} this month across {len(items)} expense(s)."
    if prev:
        answer += f" By this point last month it was {format_inr(prev)}."
    return ToolResult("category_spending", facts, answer)


def affordability(ctx: FinanceContext, amount_paise: int | None) -> ToolResult:
    if not amount_paise or amount_paise <= 0:
        return ToolResult("affordability", safe_to_spend(ctx).facts,
                          "Tell me the price, for example \"Can I afford ₹700?\", and I'll check it against your budget.",
                          verdict="need_amount")
    s = ctx.summary
    free = s.free_to_spend_paise
    days = max(1, s.days_remaining)
    new_daily = max(0, free - amount_paise) // days
    facts = [Fact("Purchase", amount_paise), Fact("Safe to spend today", s.safe_to_spend_today_paise),
             Fact("Free to spend this month", max(0, free)), Fact("Savings target", s.savings_target_paise)]
    if amount_paise <= s.safe_to_spend_today_paise:
        verdict = "yes"
        answer = f"Yes. {format_inr(amount_paise)} fits within today's safe-to-spend amount of {format_inr(s.safe_to_spend_today_paise)}."
    elif amount_paise <= free:
        verdict = "yes_with_tradeoff"
        facts.append(Fact("Daily budget after buying", new_daily))
        answer = (f"You can, but it's more than today's {format_inr(s.safe_to_spend_today_paise)}. "
                  f"Your daily budget for the rest of the month would drop to about {format_inr(new_daily)}.")
    elif amount_paise <= s.projected_end_balance_paise:
        verdict = "uses_savings"
        short = amount_paise - max(0, free)
        facts.append(Fact("Would come out of savings", short))
        answer = (f"Only by dipping into your savings: it's {format_inr(short)} more than your free money this month "
                  f"({format_inr(max(0, free))}). Consider waiting until next month.")
    else:
        verdict = "no"
        facts.append(Fact("Money left after planned expenses", max(0, s.projected_end_balance_paise)))
        answer = (f"Not right now. After your planned expenses you'll have {format_inr(max(0, s.projected_end_balance_paise))} "
                  f"left this month, which is less than {format_inr(amount_paise)}.")
    return ToolResult("affordability", facts, answer, verdict=verdict)


def spending_change(ctx: FinanceContext) -> ToolResult:
    now_total = sum(e.amount_paise for e in ctx.expenses)
    prev_items = ctx.prev_same_point()
    prev_total = sum(e.amount_paise for e in prev_items)
    cur, prev = defaultdict(int), defaultdict(int)
    for e in ctx.expenses:
        cur[e.category] += e.amount_paise
    for e in prev_items:
        prev[e.category] += e.amount_paise
    changes = sorted(((c, cur[c] - prev[c]) for c in set(cur) | set(prev)), key=lambda x: -x[1])
    facts = [Fact("Spent so far this month", now_total), Fact("Spent by this point last month", prev_total),
             Fact("Difference", now_total - prev_total)]
    ups = [(c, d) for c, d in changes if d > 0][:3]
    for c, d in ups:
        facts.append(Fact(f"{CATEGORY_LABELS[c]} increase", d))
    diff = now_total - prev_total
    if prev_total == 0 and now_total == 0:
        answer = "There's no spending to compare yet this month or last month."
    elif diff > 0:
        answer = f"You've spent {format_inr(diff)} more than by this point last month ({format_inr(now_total)} vs {format_inr(prev_total)})."
        if ups:
            answer += " The biggest increase is " + ", ".join(f"{CATEGORY_LABELS[c].lower()} (+{format_inr(d)})" for c, d in ups) + "."
    else:
        answer = f"You're actually spending {format_inr(-diff)} less than by this point last month ({format_inr(now_total)} vs {format_inr(prev_total)})."
    return ToolResult("spending_change", facts, answer)


def savings_plan(ctx: FinanceContext) -> ToolResult:
    s = ctx.summary
    weekly_target = s.savings_target_paise * 7 // ctx.period.total_days
    weeks_left = max(1, -(-s.days_remaining // 7))
    weekly_flexible = max(0, s.free_to_spend_paise) // weeks_left
    facts = [Fact("Monthly savings target", s.savings_target_paise), Fact("Weekly savings to aim for", weekly_target),
             Fact("Projected savings if you stick to plan", max(0, s.projected_end_balance_paise)),
             Fact("Flexible spending per week", weekly_flexible), Fact("Savings target protected", text=f"{s.savings_progress_pct}%")]
    if s.savings_target_paise == 0:
        answer = ("You haven't set a savings target yet. Add one on the Budget page and PocketPilot will keep it aside. "
                  f"Right now you have {format_inr(weekly_flexible)} per week for flexible spending.")
    else:
        answer = (f"Aim to save about {format_inr(weekly_target)} a week to reach your {format_inr(s.savings_target_paise)} target. "
                  f"To stay on track, keep flexible spending to about {format_inr(weekly_flexible)} per week. "
                  f"Your target is {s.savings_progress_pct}% protected right now.")
    return ToolResult("savings_plan", facts, answer)


def top_category(ctx: FinanceContext) -> ToolResult:
    if not ctx.categories:
        return ToolResult("top_category", [], "You haven't logged any expenses this month yet.")
    top = ctx.categories[0]
    label = CATEGORY_LABELS[top["category"]]
    facts = [Fact("Biggest category", text=label), Fact(f"{label} spending", top["amount_paise"]),
             Fact("Share of your spending", text=f"{top['pct']}%")]
    if len(ctx.categories) > 1:
        second = ctx.categories[1]
        facts.append(Fact(f"Next: {CATEGORY_LABELS[second['category']]}", second["amount_paise"]))
    answer = f"Your biggest expense category this month is {label.lower()} at {format_inr(top['amount_paise'])}, {top['pct']}% of your spending."
    return ToolResult("top_category", facts, answer)


def end_of_month(ctx: FinanceContext) -> ToolResult:
    s = ctx.summary
    days_so_far = max(1, ctx.period.total_days - s.days_remaining + 1)
    avg_unplanned = s.unplanned_spent_paise // days_so_far
    at_pace = s.projected_end_balance_paise - avg_unplanned * max(0, s.days_remaining - 1)
    facts = [Fact("Left if you only spend what's planned", s.projected_end_balance_paise),
             Fact("Average unplanned spending per day", avg_unplanned),
             Fact("Left if you keep your current pace", at_pace),
             Fact("Savings target", s.savings_target_paise), Fact("Days left", text=str(s.days_remaining))]
    answer = (f"If you only spend what's planned, you'll end the month with {format_inr(s.projected_end_balance_paise)}. "
              f"At your current pace of about {format_inr(avg_unplanned)} a day in unplanned spending, you'd end with "
              f"about {format_inr(at_pace)}" + (" — below your savings target." if at_pace < s.savings_target_paise else "."))
    return ToolResult("end_of_month", facts, answer)


def overview(ctx: FinanceContext) -> ToolResult:
    s = ctx.summary
    facts = [Fact("Total income", s.total_income_paise), Fact("Spent so far", s.actual_expenses_paise),
             Fact("Remaining", s.remaining_budget_paise), Fact("Reserved for planned expenses", s.reserved_upcoming_paise),
             Fact("Safe to spend today", s.safe_to_spend_today_paise), Fact("Days left", text=str(s.days_remaining))]
    answer = (f"This month you have {format_inr(s.total_income_paise)} coming in and have spent {format_inr(s.actual_expenses_paise)}. "
              f"{format_inr(s.reserved_upcoming_paise)} is set aside for planned expenses, and you can safely spend "
              f"{format_inr(s.safe_to_spend_today_paise)} today.")
    return ToolResult("overview", facts, answer)


def run_tool(ctx: FinanceContext, tool: str, *, category: str | None = None, amount_paise: int | None = None) -> ToolResult:
    if tool == "safe_to_spend":
        return safe_to_spend(ctx)
    if tool == "category_spending":
        return category_spending(ctx, category)
    if tool == "affordability":
        return affordability(ctx, amount_paise)
    if tool == "spending_change":
        return spending_change(ctx)
    if tool == "savings_plan":
        return savings_plan(ctx)
    if tool == "top_category":
        return top_category(ctx)
    if tool == "end_of_month":
        return end_of_month(ctx)
    return overview(ctx)
