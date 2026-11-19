"""Test fixtures: a scriptable fake Bifrost gateway and fake Tavily API built on
httpx.MockTransport, so the full pipeline runs offline and deterministically."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from freshguard.bifrost_client import BifrostClient  # noqa: E402
from freshguard.config import Settings  # noqa: E402
from freshguard.pipeline import FreshGuardEngine  # noqa: E402
from freshguard.tavily_client import TavilyClient  # noqa: E402

STAGE_MARKERS = [
    ("extract", "claim-extraction stage"),
    ("vet", "evidence-vetting agent"),
    ("verify", "verification agent of FreshGuard"),
    ("audit", "independent hallucination auditor for FreshGuard"),
]


def make_settings(**overrides: Any) -> Settings:
    base = Settings(
        tavily_api_key="tvly-test",
        bifrost_base_url="http://bifrost.test/v1",
        bifrost_api_key="",
        primary_model="groq/primary",
        fallback_models=["groq/fallback"],
        auditor_model="groq/auditor",
        auditor_fallbacks=[],
        max_claims=12,
        max_verification_attempts=3,
        claim_concurrency=4,
        llm_timeout_seconds=5,
        claim_timeout_seconds=20,
        analysis_timeout_seconds=30,
        allowed_origins=["http://localhost:8005"],
    )
    return replace(base, **overrides)


class FakeLLM:
    """Responds per pipeline stage. Each stage has a queue of responses (dict -> JSON,
    str -> raw text, callable(request_json) -> dict); the last item repeats."""

    def __init__(self) -> None:
        self.responses: Dict[str, List[Any]] = {}
        self.calls: List[Dict[str, Any]] = []
        self.down = False
        self.rate_limit_remaining = 0  # respond 429 to this many calls first

    def on(self, stage: str, *responses: Any) -> "FakeLLM":
        self.responses[stage] = list(responses)
        return self

    def stage_of(self, body: Dict[str, Any]) -> str:
        system = body["messages"][0]["content"]
        for stage, marker in STAGE_MARKERS:
            if marker in system:
                return stage
        return "unknown"

    def count(self, stage: str) -> int:
        return sum(1 for c in self.calls if c["stage"] == stage)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("bifrost down", request=request)
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        body = json.loads(request.content)
        if self.rate_limit_remaining > 0:
            self.rate_limit_remaining -= 1
            return httpx.Response(429, text='{"error":{"message":"Rate limit reached on tokens per minute. Please try again in 0.01s."}}')
        stage = self.stage_of(body)
        self.calls.append({"stage": stage, "body": body})
        queue = self.responses.get(stage)
        if not queue:
            return httpx.Response(500, json={"error": f"no fake response for stage {stage}"})
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(item):
            item = item(body)
        content = item if isinstance(item, str) else json.dumps(item)
        return httpx.Response(200, json={"model": body["model"], "choices": [{"message": {"content": content}}]})


class FakeTavily:
    def __init__(self, results: Optional[List[Dict[str, Any]]] = None, answer: str = "") -> None:
        self.results = results or []
        self.answer = answer
        self.queries: List[Dict[str, Any]] = []
        self.down = False
        self.by_query: Optional[Callable[[str], List[Dict[str, Any]]]] = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, text="unavailable")
        body = json.loads(request.content)
        self.queries.append(body)
        assert request.headers.get("authorization") == "Bearer tvly-test"
        results = self.by_query(body["query"]) if self.by_query else self.results
        return httpx.Response(200, json={"query": body["query"], "answer": self.answer, "results": results})


def tavily_result(url: str, content: str, title: str = "Source", published: Optional[str] = "2026-11-01", score: float = 0.9) -> Dict[str, Any]:
    return {"url": url, "title": title, "content": content, "published_date": published, "score": score}


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_tavily() -> FakeTavily:
    return FakeTavily()


@pytest.fixture
def make_engine(fake_llm: FakeLLM, fake_tavily: FakeTavily):
    def _make(**overrides: Any) -> FreshGuardEngine:
        s = make_settings(**overrides)
        gateway = BifrostClient(s, transport=httpx.MockTransport(fake_llm.handler))
        tavily = TavilyClient(s, transport=httpx.MockTransport(fake_tavily.handler))
        return FreshGuardEngine(s, gateway=gateway, tavily=tavily)

    return _make
