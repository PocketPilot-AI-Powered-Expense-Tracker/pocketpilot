from tests.conftest import auth_headers, register


def test_register_returns_token_and_user(client, db):
    data = register(client)
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "asha@example.com"
    assert data["user"]["has_budget"] is False
    assert "password" not in str(data)


def test_password_is_hashed_not_stored_plain(client, db):
    register(client, password="secret123")
    import asyncio

    stored = asyncio.run(db.users.find_one({"email": "asha@example.com"}))
    assert "password" not in stored
    assert stored["password_hash"] != "secret123"
    assert stored["password_hash"].startswith("$2")


def test_duplicate_email_rejected_case_insensitive(client):
    register(client, email="asha@example.com")
    res = client.post("/api/auth/register", json={"name": "A", "email": "ASHA@example.com", "password": "secret123"})
    assert res.status_code == 409


def test_weak_password_rejected(client):
    res = client.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "short"})
    assert res.status_code == 422
    res = client.post("/api/auth/register", json={"name": "A", "email": "a@example.com", "password": "onlyletters"})
    assert res.status_code == 422


def test_login_success_and_me(client):
    register(client)
    res = client.post("/api/auth/login", json={"email": "Asha@Example.com", "password": "secret123"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["name"] == "Asha"


def test_login_wrong_password(client):
    register(client)
    res = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong1234"})
    assert res.status_code == 401


def test_login_unknown_email(client):
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "secret123"})
    assert res.status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/budget").status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers("not-a-jwt")).status_code == 401


def test_token_with_wrong_secret_rejected(client):
    import jwt

    register(client)
    forged = jwt.encode({"sub": "000000000000000000000000", "type": "access"}, "x" * 40, algorithm="HS256")
    assert client.get("/api/auth/me", headers=auth_headers(forged)).status_code == 401
