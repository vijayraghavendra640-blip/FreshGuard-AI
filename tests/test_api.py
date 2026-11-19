"""API contract tests (FastAPI TestClient) with the fake gateway and fake Tavily."""
import json

import pytest
from fastapi.testclient import TestClient

import freshguard.pipeline as pipeline
from conftest import tavily_result


@pytest.fixture
def client(make_engine, monkeypatch):
    engine = make_engine()
    monkeypatch.setattr(pipeline, "_ENGINE", engine)
    import main
    return TestClient(main.app)


def test_empty_text_is_rejected(client):
    assert client.post("/api/verify", json={"text": "   "}).status_code == 422
    assert client.post("/api/verify", json={}).status_code == 422


def test_answer_generation_endpoint_is_not_exposed(client):
    # The problem statement asks to verify an existing LLM answer, not to generate one.
    assert client.post("/api/generate-and-verify", json={"prompt": "x"}).status_code in (404, 405)


def test_guardrail_blocks_when_verification_is_unavailable(client, fake_llm, fake_tavily):
    fake_llm.down = True
    fake_tavily.results = [tavily_result("https://apple.com/leadership", "Tim Cook is the CEO of Apple.")]
    r = client.post("/api/guardrail", json={"text": "Tim Cook is the CEO of Apple."})
    body = r.json()
    assert r.status_code == 200
    assert body["guardrail_passed"] is False and body["action"] == "BLOCK_DEPLOY"


def test_cache_clear_requires_configured_token(client):
    assert client.post("/api/cache/clear").status_code == 403
    assert client.post("/api/cache/clear", headers={"X-Admin-Token": "anything"}).status_code == 403


def test_health_reports_gateway(client):
    body = client.get("/api/health").json()
    assert body["tavily_configured"] is True
    assert body["bifrost"]["reachable"] is True
    assert body["bifrost"]["primary_model"] == "groq/primary"


def test_stream_endpoint_emits_sse_events(client, fake_llm, fake_tavily):
    fake_llm.down = True
    with client.stream("POST", "/api/verify/stream", json={"text": "Tim Cook is the CEO of Apple."}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[-1] == "done" and "report" in types
    report = next(e["report"] for e in events if e["type"] == "report")
    assert report["overall_verdict"] == "Needs Review"


def test_security_headers_present(client):
    r = client.get("/api/presets")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert len(r.json()["presets"]) >= 4
