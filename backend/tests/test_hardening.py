"""Production-readiness: account deletion, login throttling, health, settings checks, errors."""
from app.core.config import Settings
from tests.conftest import auth_headers, register


def test_delete_account_removes_everything(client, budget_user, other_user, db):
    import asyncio

    h = budget_user["headers"]
    client.post("/api/expenses", json={"amount_paise": 100, "category": "food", "description": "x", "date": "2026-11-15"}, headers=h)
    client.post("/api/routines", json={"name": "Tea", "amount_paise": 3000, "category": "food", "frequency": "daily"}, headers=h)
    client.get("/api/occurrences", headers=h)
    client.post("/api/pending-transactions", headers=h, json={"amount_paise": 500, "source_app": "gpay",
                "transaction_ref": "123456789012", "detected_at": "2026-11-15T10:00:00+05:30"})
    assert client.delete("/api/auth/me", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    for name in ("users", "budgets", "expenses", "recurring_rules", "planned_occurrences", "pending_transactions"):
        docs = asyncio.run(db[name].find({}).to_list(None))
        assert all(str(d.get("user_id", d["_id"])) == other_user["id"] for d in docs), name
    # The other user is untouched
    assert client.get("/api/budget", headers=other_user["headers"]).status_code == 200


def test_login_is_throttled(client):
    register(client)
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong1234"}).status_code == 401
    res = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "secret123"})
    assert res.status_code == 429


def test_health_and_ready(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/health/ready").json() == {"status": "ok", "database": "ok"}


def test_production_settings_are_checked():
    bad = Settings(ENVIRONMENT="production", JWT_SECRET="demo-secret-key-that-is-long-enough-123456",
                   MONGODB_URI="mongodb://localhost:27017", FRONTEND_URL="http://pocketpilot.example.com")
    assert len(bad.production_problems()) == 3
    good = Settings(ENVIRONMENT="production", JWT_SECRET="Zq8x-Lw2vR9pK4mT7yB1nC6hF3jD5sG0aE_uI",
                    MONGODB_URI="mongodb+srv://u:p@cluster0.abc.mongodb.net", FRONTEND_URL="https://pocketpilot.vercel.app")
    assert good.production_problems() == []
    assert Settings(JWT_SECRET="x" * 40).production_problems() == []  # development: no checks


def test_unexpected_errors_return_clean_500(client, budget_user, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import analytics_service

    async def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(analytics_service, "safe_to_spend", boom)
    res = TestClient(app, raise_server_exceptions=False).get("/api/analytics/safe-to-spend", headers=budget_user["headers"])
    assert res.status_code == 500 and "secret" not in res.text
