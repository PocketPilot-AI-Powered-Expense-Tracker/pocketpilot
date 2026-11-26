from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = hash_password("dummy-password-1")


async def user_out(db, user: dict) -> UserOut:
    has_budget = await db.budgets.find_one({"user_id": user["_id"]}, {"_id": 1}) is not None
    return UserOut(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        created_at=user["created_at"],
        has_budget=has_budget,
    )


async def register(db, data: RegisterRequest) -> TokenResponse:
    doc = {
        "name": data.name,
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    doc["_id"] = result.inserted_id
    token, expires_in = create_access_token(str(doc["_id"]))
    return TokenResponse(access_token=token, expires_in=expires_in, user=await user_out(db, doc))


async def login(db, data: LoginRequest) -> TokenResponse:
    user = await db.users.find_one({"email": data.email.lower()})
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token, expires_in = create_access_token(str(user["_id"]))
    return TokenResponse(access_token=token, expires_in=expires_in, user=await user_out(db, user))


USER_COLLECTIONS = ("budgets", "expenses", "income", "recurring_rules", "planned_occurrences",
                    "pending_transactions", "ai_proposals", "ai_cache")


async def delete_account(db, user_id) -> None:
    """Remove every record belonging to the user, then the user."""
    for name in USER_COLLECTIONS:
        await db[name].delete_many({"user_id": user_id})
    await db.users.delete_one({"_id": user_id})
