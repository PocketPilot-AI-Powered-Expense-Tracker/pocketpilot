"""'Today' in the app's timezone. Tests monkeypatch app_today()."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def app_today() -> date:
    return datetime.now(ZoneInfo(get_settings().APP_TIMEZONE)).date()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
