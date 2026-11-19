"""Client for the Bifrost AI gateway (OpenAI-compatible API).

Every LLM call FreshGuard makes goes through this client: claim extraction,
source vetting, verification, hallucination auditing, answer rewriting and
answer generation. Provider routing, retries and model fallbacks are handled
by Bifrost; FreshGuard only names a primary model plus a fallback chain.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

from .config import Settings, get_settings

logger = logging.getLogger("freshguard.bifrost")


class BifrostError(RuntimeError):
    """Raised when the gateway cannot return a usable completion."""

    def __init__(self, message: str, status: int = 0, rate_limited: bool = False):
        super().__init__(message)
        self.status = status
        self.rate_limited = rate_limited


_RETRY_AFTER_RE = re.compile(r"try again in\s+(?:(\d+)m)?\s*([\d.]+)\s*(ms|s)(?![a-z])", re.IGNORECASE)


def retry_after_seconds(resp: httpx.Response) -> Optional[float]:
    """Seconds to wait before retrying a 429, from Retry-After or the provider's message."""
    header = resp.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = _RETRY_AFTER_RE.search(resp.text or "")
    if m:
        minutes = float(m.group(1) or 0)
        value = float(m.group(2))
        return minutes * 60 + (value / 1000 if m.group(3).lower() == "ms" else value)
    return None


@dataclass
class LLMResult:
    data: Any
    model: str
    provider: str
    is_fallback: bool
    latency_ms: int
    raw_text: str = ""


@dataclass
class GatewayStats:
    calls: int = 0
    failures: int = 0
    fallbacks_used: int = 0
    json_repairs: int = 0
    rate_limit_waits: int = 0
    by_model: Dict[str, int] = field(default_factory=dict)
    last_error: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "failures": self.failures,
            "fallbacks_used": self.fallbacks_used,
            "json_repairs": self.json_repairs,
            "rate_limit_waits": self.rate_limit_waits,
            "by_model": dict(self.by_model),
            "last_error": self.last_error,
        }


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object from model output, tolerating <think> blocks and code fences."""
    if not text:
        raise ValueError("empty completion")
    cleaned = _THINK_RE.sub("", text).strip()
    cleaned = _FENCE_RE.sub("", cleaned).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in completion")
        obj = json.loads(cleaned[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("completion JSON is not an object")
    return obj


class BifrostClient:
    def __init__(self, settings: Optional[Settings] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings or get_settings()
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None
        self.stats = GatewayStats()
        # Caps in-flight model calls so parallel claims do not exhaust provider rate limits.
        self._slots = asyncio.Semaphore(self.settings.llm_concurrency)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds, transport=self._transport)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.bifrost_api_key:
            headers["Authorization"] = f"Bearer {self.settings.bifrost_api_key}"
        return headers

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        fallbacks: Optional[List[str]] = None,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1200,
    ) -> LLMResult:
        model = model or self.settings.primary_model
        chain = self.settings.fallback_models if fallbacks is None else fallbacks
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        chain = [m for m in chain if m and m != model]
        if chain:
            body["fallbacks"] = chain
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.settings.reasoning_effort in ("low", "medium", "high"):
            body["reasoning_effort"] = self.settings.reasoning_effort

        self.stats.calls += 1
        started = time.perf_counter()
        attempt = 0
        while True:
            attempt += 1
            try:
                async with self._slots:
                    resp = await self._http().post(self.settings.bifrost_chat_url, headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                self.stats.failures += 1
                self.stats.last_error = f"gateway unreachable: {type(exc).__name__}"
                raise BifrostError(self.stats.last_error) from exc
            if resp.status_code == 429:
                wait = retry_after_seconds(resp)
                wait = 2.0 * attempt if wait is None else wait
                if attempt <= self.settings.rate_limit_retries and wait <= self.settings.rate_limit_max_wait_seconds:
                    self.stats.rate_limit_waits += 1
                    logger.info("Rate limited on %s; retrying in %.1fs (attempt %d)", model, wait, attempt)
                    await asyncio.sleep(wait + 0.25)
                    continue
                self.stats.failures += 1
                self.stats.last_error = f"HTTP 429: {resp.text[:300]}"
                raise BifrostError("model provider rate limit reached", status=429, rate_limited=True)
            break
        latency = int((time.perf_counter() - started) * 1000)

        if resp.status_code != 200:
            self.stats.failures += 1
            detail = resp.text[:300]
            self.stats.last_error = f"HTTP {resp.status_code}: {detail}"
            logger.warning("Bifrost returned %s for model %s: %s", resp.status_code, model, detail)
            raise BifrostError(self.stats.last_error, status=resp.status_code)

        try:
            payload = resp.json()
            text = payload["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            self.stats.failures += 1
            self.stats.last_error = "malformed gateway response"
            raise BifrostError(self.stats.last_error) from exc

        routing = ((payload.get("extra_fields") or {}).get("routing_info") or {}) if isinstance(payload, dict) else {}
        served_model = routing.get("model") or payload.get("model") or model
        provider = routing.get("provider") or (model.split("/", 1)[0] if "/" in model else "unknown")
        is_fallback = bool(routing.get("is_fallback"))
        if is_fallback:
            self.stats.fallbacks_used += 1
        self.stats.by_model[served_model] = self.stats.by_model.get(served_model, 0) + 1
        return LLMResult(data=text, model=served_model, provider=provider, is_fallback=is_fallback, latency_ms=latency, raw_text=text)

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        model: Optional[str] = None,
        fallbacks: Optional[List[str]] = None,
        validator: Optional[Callable[[Dict[str, Any]], Any]] = None,
        max_tokens: int = 1500,
    ) -> LLMResult:
        """Request a JSON object. If the output is not valid JSON, or fails `validator`,
        the request is re-sent once with the error explained to the model."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        last_error = ""
        for attempt in range(2):
            result = await self.chat(messages, model=model, fallbacks=fallbacks, json_mode=True, max_tokens=max_tokens)
            if not result.raw_text.strip():
                last_error = "empty completion (likely truncated by max_tokens)"
                self.stats.json_repairs += 1
                max_tokens = int(max_tokens * 1.5)
                continue
            try:
                obj = parse_json_object(result.raw_text)
                result.data = validator(obj) if validator else obj
                return result
            except (ValueError, TypeError, KeyError) as exc:
                last_error = str(exc)[:200]
                self.stats.json_repairs += 1
                messages = messages[:2] + [
                    {"role": "assistant", "content": result.raw_text[:2000]},
                    {"role": "user", "content": f"Your previous reply was rejected: {last_error}. Reply again with ONLY a valid JSON object that follows the required schema."},
                ]
        self.stats.failures += 1
        self.stats.last_error = f"invalid JSON after retry: {last_error}"
        raise BifrostError(self.stats.last_error)

    async def health(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "base_url": self.settings.bifrost_base_url,
            "direct_provider_url": self.settings.bifrost_looks_direct_provider,
            "primary_model": self.settings.primary_model,
            "fallback_models": self.settings.fallback_models,
            "auditor_model": self.settings.auditor_model,
        }
        try:
            r = await self._http().get(f"{self.settings.bifrost_root_url}/health", timeout=4.0)
            info["reachable"] = r.status_code == 200
        except httpx.HTTPError:
            info["reachable"] = False
        return info
