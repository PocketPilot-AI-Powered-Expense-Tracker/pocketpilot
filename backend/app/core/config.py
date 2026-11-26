"""Application settings, loaded from environment variables (or a local .env file)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "production" turns on startup safety checks (see production_problems()).
    ENVIRONMENT: str = "development"

    MONGODB_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "pocketpilot"

    # No default on purpose: the app refuses to start without a real secret.
    JWT_SECRET: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Which AI provider to use: "groq", "gemini", or "none" (built-in rule-based answers only).
    AI_PROVIDER: str = "groq"

    GROQ_API_KEY: str = ""
    # Check https://console.groq.com/docs/models for current ids.
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    # For reasoning models (gpt-oss): low | medium | high, or empty to omit.
    GROQ_REASONING_EFFORT: str = "low"

    GEMINI_API_KEY: str = ""
    # Model id is configurable; check https://ai.google.dev/gemini-api/docs/models for current ones.
    GEMINI_MODEL: str = "gemini-3.8-flash"
    # minimal | low | medium | high, or empty to use the model default.
    GEMINI_THINKING_LEVEL: str = "low"
    GEMINI_TIMEOUT_SECONDS: int = 20
    AI_TIMEOUT_SECONDS: int = 20
    # Per-user limit on AI requests (protects your API quota).
    AI_RATE_LIMIT_PER_10_MIN: int = 30

    # "Today" is decided in the students' timezone, not the server's (Render runs in UTC).
    APP_TIMEZONE: str = "Asia/Kolkata"

    # Lets users feed sample UPI notifications to test the review flow.
    ENABLE_NOTIFICATION_SIMULATOR: bool = True

    # Comma-separated list of allowed frontend origins for CORS.
    FRONTEND_URL: str = "http://localhost:5173"

    def production_problems(self) -> list[str]:
        """Settings that are unsafe in production. The app refuses to start if any are found."""
        if self.ENVIRONMENT.lower() != "production":
            return []
        problems = []
        if "localhost" in self.MONGODB_URI or "127.0.0.1" in self.MONGODB_URI:
            problems.append("MONGODB_URI points to localhost")
        if "demo" in self.JWT_SECRET.lower() or "test" in self.JWT_SECRET.lower() or len(set(self.JWT_SECRET)) < 10:
            problems.append("JWT_SECRET looks like a placeholder; generate a random one")
        if any(o.startswith("http://") and "localhost" not in o for o in self.cors_origins):
            problems.append("FRONTEND_URL should use https in production")
        return problems

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.FRONTEND_URL.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
