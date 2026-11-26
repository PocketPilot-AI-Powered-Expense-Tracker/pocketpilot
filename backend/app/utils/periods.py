"""Budget period calculation.

A budget period is one "month" that starts on the user's chosen day
(e.g. the day their allowance arrives). With start_day=5, the period
containing 2026-11-03 is 2026-10-05 .. 2026-11-04 (inclusive).
start_day is limited to 1..28 so every month contains it.
"""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Period:
    start: date
    end: date  # inclusive

    @property
    def total_days(self) -> int:
        return (self.end - self.start).days + 1

    def days_remaining(self, today: date) -> int:
        """Days left including today. 0 if the period is over."""
        if today > self.end:
            return 0
        if today < self.start:
            return self.total_days
        return (self.end - today).days + 1


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def period_containing(day: date, start_day: int) -> Period:
    if not 1 <= start_day <= 28:
        raise ValueError("start_day must be between 1 and 28")
    if day.day >= start_day:
        sy, sm = day.year, day.month
    else:
        sy, sm = _add_months(day.year, day.month, -1)
    start = date(sy, sm, start_day)
    ny, nm = _add_months(sy, sm, 1)
    end = date(ny, nm, start_day) - timedelta(days=1)
    return Period(start=start, end=end)
