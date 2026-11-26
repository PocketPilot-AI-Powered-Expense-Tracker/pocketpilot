import os

os.environ.setdefault("JWT_SECRET", "test-secret-key-that-is-long-enough-for-hs256")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.mongo import ensure_indexes, get_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.fake_db import FakeDatabase  # noqa: E402


@pytest.fixture
def db():
    fake = FakeDatabase()
    asyncio.run(ensure_indexes(fake))
    return fake


import datetime as _dt  # noqa: E402

TODAY = _dt.date(2026, 11, 15)  # period 1–30 Nov, 16 days left incl. today
NOW = _dt.datetime(2026, 11, 15, 6, 30, tzinfo=_dt.timezone.utc)  # 12:00 IST on TODAY


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    """Freeze the app's notion of 'today' so date maths in tests is predictable."""
    from app.utils import dates

    monkeypatch.setattr(dates, "app_today", lambda: TODAY)
    monkeypatch.setattr(dates, "utc_now", lambda: NOW)
    return TODAY


class FakeAI:
    """Scriptable stand-in for Gemini. Records every prompt it receives."""
    name = "fake"

    def __init__(self):
        self.prompts: list[str] = []
        self.json_responses: list = []  # pydantic objects, or Exception instances to raise
        self.text_responses: list = []

    async def generate_json(self, *, system, prompt, schema):
        self.prompts.append(prompt)
        item = self.json_responses.pop(0) if self.json_responses else None
        if item is None or isinstance(item, Exception):
            from app.ai.provider import AIUnavailable
            raise item or AIUnavailable("no scripted response")
        return item

    async def generate_text(self, *, system, prompt):
        self.prompts.append(prompt)
        item = self.text_responses.pop(0) if self.text_responses else None
        if item is None or isinstance(item, Exception):
            from app.ai.provider import AIUnavailable
            raise item or AIUnavailable("no scripted response")
        return item


@pytest.fixture
def client(db):
    from app.ai.provider import get_ai_provider
    from app.core import rate_limit

    rate_limit.reset()
    app.dependency_overrides[get_db] = lambda: db
    # By default tests run with NO AI (even if a real key is in the environment).
    app.dependency_overrides[get_ai_provider] = lambda: None
    # Not used as a context manager, so the real Mongo lifespan never runs.
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="asha@example.com", password="secret123", name="Asha"):
    res = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert res.status_code == 201, res.text
    return res.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user(client):
    data = register(client)
    return {"token": data["access_token"], "headers": auth_headers(data["access_token"]), **data["user"]}


BUDGET = {
    "monthly_allowance_paise": 800000,  # ₹8,000
    "additional_income_paise": 50000,  # ₹500
    "savings_target_paise": 150000,  # ₹1,500
    "period_start_day": 1,
}


@pytest.fixture
def budget_user(client, user):
    res = client.post("/api/budget", json=BUDGET, headers=user["headers"])
    assert res.status_code == 201, res.text
    return user


@pytest.fixture
def other_user(client):
    data = register(client, email="ravi@example.com", name="Ravi")
    headers = auth_headers(data["access_token"])
    client.post("/api/budget", json=BUDGET, headers=headers)
    return {"headers": headers, **data["user"]}


@pytest.fixture
def fake_ai(client):
    from app.ai.provider import get_ai_provider

    ai = FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: ai
    return ai
