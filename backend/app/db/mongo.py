"""MongoDB connection (PyMongo Async API) and index setup."""
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

_client: AsyncMongoClient | None = None


def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(get_settings().MONGODB_URI, tz_aware=True, serverSelectionTimeoutMS=10000)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_db() -> AsyncDatabase:
    """FastAPI dependency. Tests override this with an in-memory database."""
    return get_client()[get_settings().DATABASE_NAME]


async def ensure_indexes(db) -> None:
    """Create indexes. Safe to run on every startup (create_index is idempotent)."""
    await db.users.create_index([("email", ASCENDING)], unique=True)
    # One active budget plan per user.
    await db.budgets.create_index([("user_id", ASCENDING)], unique=True)
    await db.expenses.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    await db.expenses.create_index([("user_id", ASCENDING), ("category", ASCENDING), ("date", DESCENDING)])
    # A planned occurrence can produce at most one expense ("mark spent exactly once").
    await db.expenses.create_index([("occurrence_id", ASCENDING)], unique=True, sparse=True)
    await db.income.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
    await db.recurring_rules.create_index([("user_id", ASCENDING), ("active", ASCENDING)])
    # One occurrence per rule per original date: generation is idempotent and
    # rescheduling (which changes scheduled_date only) never creates a duplicate.
    await db.planned_occurrences.create_index([("rule_id", ASCENDING), ("original_date", ASCENDING)], unique=True)
    await db.planned_occurrences.create_index([("user_id", ASCENDING), ("scheduled_date", ASCENDING)])
    # An accepted pending transaction can produce at most one expense.
    await db.expenses.create_index([("pending_id", ASCENDING)], unique=True, sparse=True)
    # Duplicate detection. Both keys already include the user, and are only set when known.
    await db.pending_transactions.create_index([("dedupe_ref", ASCENDING)], unique=True, sparse=True)
    await db.pending_transactions.create_index([("dedupe_hash", ASCENDING)], unique=True, sparse=True)
    await db.pending_transactions.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("detected_at", DESCENDING)])
    # AI: proposals auto-delete after a day; cached AI text after 12 hours.
    await db.ai_proposals.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.ai_proposals.create_index([("created_at", ASCENDING)], expireAfterSeconds=86400, name="ai_proposals_ttl")
    await db.ai_cache.create_index([("user_id", ASCENDING), ("kind", ASCENDING)], unique=True)
    await db.ai_cache.create_index([("created_at", ASCENDING)], expireAfterSeconds=43200, name="ai_cache_ttl")
