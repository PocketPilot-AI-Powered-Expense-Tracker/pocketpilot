"""AI provider interface.

PocketPilot talks to AI models only through this small interface, so Gemini can be
swapped for another model by adding one class. Providers receive prompt text and
return text / validated JSON. They have NO database access and NO way to change data.
"""
from functools import lru_cache
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class AIUnavailable(Exception):
    """The AI call failed (no key, network, quota, bad output). Callers fall back to rules."""


class AIProvider(Protocol):
    name: str

    async def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T: ...

    async def generate_text(self, *, system: str, prompt: str) -> str: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, thinking_level: str = "", timeout_seconds: int = 20):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000))
        self.model = model
        self._thinking = thinking_level.strip().upper() or None

    async def _generate(self, system: str, prompt: str, **extra) -> str:
        t = self._types
        config = t.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=2048,
            thinking_config=t.ThinkingConfig(thinking_level=self._thinking) if self._thinking else None,
            **extra,
        )
        try:
            response = await self._client.aio.models.generate_content(model=self.model, contents=prompt, config=config)
        except Exception as e:  # network, auth, quota, invalid model...
            raise AIUnavailable(f"{type(e).__name__}: {e}") from e
        text = (response.text or "").strip()
        if not text:
            raise AIUnavailable("Empty response from model")
        return text

    async def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        text = await self._generate(system, prompt, response_mime_type="application/json",
                                    response_json_schema=schema.model_json_schema())
        try:
            return schema.model_validate_json(text)
        except ValidationError as e:
            raise AIUnavailable(f"Model returned invalid JSON: {e.error_count()} errors") from e

    async def generate_text(self, *, system: str, prompt: str) -> str:
        return await self._generate(system, prompt)


@lru_cache
def _configured_provider() -> "AIProvider | None":
    s = get_settings()
    choice = s.AI_PROVIDER.strip().lower()
    if choice == "groq" and s.GROQ_API_KEY:
        from app.ai.groq_provider import GroqProvider

        return GroqProvider(s.GROQ_API_KEY, s.GROQ_MODEL, s.GROQ_REASONING_EFFORT, s.AI_TIMEOUT_SECONDS)
    if choice == "gemini" and s.GEMINI_API_KEY:
        return GeminiProvider(s.GEMINI_API_KEY, s.GEMINI_MODEL, s.GEMINI_THINKING_LEVEL, s.GEMINI_TIMEOUT_SECONDS)
    return None


def get_ai_provider() -> AIProvider | None:
    """FastAPI dependency. Chosen by AI_PROVIDER (groq | gemini | none).
    None means "no AI configured": features use rule-based fallbacks.
    Tests override this with a fake provider."""
    return _configured_provider()
