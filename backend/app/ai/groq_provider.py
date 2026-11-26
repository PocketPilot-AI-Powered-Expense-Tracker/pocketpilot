"""Groq provider (OpenAI-compatible Chat Completions API), called with httpx.

Structured output uses `response_format: json_schema` with `strict: true`. If the model
rejects the schema, we retry once without `strict`; the reply is always re-validated
with Pydantic, so a bad reply can never reach the app.
"""
import copy

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.provider import AIUnavailable

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Keywords strict JSON-schema mode may not accept. Pydantic enforces them afterwards anyway.
_DROP = {"title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
         "minLength", "maxLength", "pattern", "format", "minItems", "maxItems"}


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema -> strict-mode friendly schema:
    $refs inlined, every property required, no additional properties, unsupported keywords removed."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, list):
            return [walk(x) for x in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
        out = {k: walk(v) for k, v in node.items() if k not in _DROP}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    return walk(schema)


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, model: str, reasoning_effort: str = "", timeout_seconds: int = 20,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.model = model
        self._key = api_key
        self._effort = reasoning_effort.strip().lower() or None
        self._timeout = timeout_seconds
        self._transport = transport  # tests inject a mock transport

    async def _chat(self, system: str, prompt: str, response_format: dict | None = None) -> str:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_completion_tokens": 2048,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        if response_format:
            body["response_format"] = response_format
        if self._effort and "gpt-oss" in self.model:
            body["reasoning_effort"] = self._effort
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                r = await client.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {self._key}"})
        except httpx.HTTPError as e:
            raise AIUnavailable(f"Groq request failed: {type(e).__name__}") from e
        if r.status_code != 200:
            # Never include the request (it has the key) in the error; a short body excerpt is enough.
            raise AIUnavailable(f"Groq HTTP {r.status_code}: {r.text[:200]}")
        try:
            text = (r.json()["choices"][0]["message"].get("content") or "").strip()
        except (ValueError, KeyError, IndexError) as e:
            raise AIUnavailable("Unexpected Groq response shape") from e
        if not text:
            raise AIUnavailable("Empty response from Groq")
        return text

    async def generate_json(self, *, system: str, prompt: str, schema: type[BaseModel]):
        fmt = {"type": "json_schema", "json_schema": {"name": schema.__name__, "strict": True, "schema": strict_schema(schema)}}
        try:
            text = await self._chat(system, prompt, fmt)
        except AIUnavailable as e:
            if "HTTP 400" not in str(e):
                raise
            # Model/schema combination not accepted in strict mode: try best-effort schema mode.
            fmt["json_schema"]["strict"] = False
            text = await self._chat(system, prompt, fmt)
        try:
            return schema.model_validate_json(text)
        except ValidationError as e:
            raise AIUnavailable(f"Groq returned JSON that failed validation ({e.error_count()} errors)") from e

    async def generate_text(self, *, system: str, prompt: str) -> str:
        return await self._chat(system, prompt)
