"""GroqProvider tested with a mock HTTP transport (no network, no real key)."""
import asyncio
import json

import httpx
import pytest

from app.ai.groq_provider import GroqProvider, strict_schema
from app.ai.guard import clean_text
from app.ai.provider import AIUnavailable
from app.schemas.ai import ActionAI, InsightTips, RoutePlan


def make(handler, model="openai/gpt-oss-120b"):
    return GroqProvider("gsk_test", model, "low", 5, transport=httpx.MockTransport(handler))


def reply(content, status=200):
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def run(coro):
    return asyncio.run(coro)


def test_strict_schema_is_closed_and_inlined():
    s = strict_schema(InsightTips)
    assert "$defs" not in json.dumps(s) and "$ref" not in json.dumps(s)
    assert s["additionalProperties"] is False and s["required"] == ["tips"]
    item = s["properties"]["tips"]["items"]
    assert item["required"] == ["id", "tip"] and item["additionalProperties"] is False
    a = strict_schema(ActionAI)
    assert set(a["required"]) == set(ActionAI.model_fields)  # every field required in strict mode
    assert "default" not in json.dumps(a) and "title" not in json.dumps(a)


def test_generate_json_sends_strict_schema_and_validates():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return reply('{"tool": "affordability", "category": null, "amount_rupees": 700}')

    plan = run(make(handler).generate_json(system="s", prompt="p", schema=RoutePlan))
    assert plan.tool == "affordability" and plan.amount_rupees == 700
    body = seen["body"]
    assert seen["auth"] == "Bearer gsk_test"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["reasoning_effort"] == "low" and body["model"] == "openai/gpt-oss-120b"


def test_reasoning_effort_only_for_gpt_oss():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return reply("hello")

    run(make(handler, model="qwen/qwen3.8-27b").generate_text(system="s", prompt="p"))
    assert "reasoning_effort" not in seen["body"]


def test_falls_back_to_non_strict_on_400():
    calls = []

    def handler(request):
        strict = json.loads(request.content)["response_format"]["json_schema"]["strict"]
        calls.append(strict)
        return httpx.Response(400, json={"error": "schema not supported"}) if strict else reply('{"tool": "overview"}')

    assert run(make(handler).generate_json(system="s", prompt="p", schema=RoutePlan)).tool == "overview"
    assert calls == [True, False]


@pytest.mark.parametrize("response", [
    httpx.Response(429, json={"error": "rate limited"}),
    httpx.Response(401, json={"error": "bad key"}),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": '{"tool": "not-a-tool"}'}}]}),
])
def test_errors_become_ai_unavailable(response):
    with pytest.raises(AIUnavailable) as e:
        run(make(lambda r: response).generate_json(system="s", prompt="p", schema=RoutePlan))
    assert "gsk_test" not in str(e.value)  # never leak the key


def test_network_error_becomes_ai_unavailable():
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(AIUnavailable):
        run(make(handler).generate_text(system="s", prompt="p"))


def test_provider_selection(monkeypatch):
    from app.ai import provider
    from app.core.config import get_settings

    s = get_settings()
    for choice, groq_key, gemini_key, expected in [
        ("groq", "gsk_x", "", "groq"), ("groq", "", "", None), ("none", "gsk_x", "", None),
        ("gemini", "gsk_x", "", None), ("gemini", "", "AIza-x", "gemini"),
    ]:
        monkeypatch.setattr(s, "AI_PROVIDER", choice)
        monkeypatch.setattr(s, "GROQ_API_KEY", groq_key)
        monkeypatch.setattr(s, "GEMINI_API_KEY", gemini_key)
        provider._configured_provider.cache_clear()
        got = provider.get_ai_provider()
        assert (got.name if got else None) == expected, choice
    provider._configured_provider.cache_clear()


def test_clean_text_strips_markdown():
    assert clean_text("You can spend ₹62.29.\n\n**Tip:** Track it.\n## Note\n- one\n* two") == \
        "You can spend ₹62.29.\n\nTip: Track it.\nNote\n• one\n• two"
