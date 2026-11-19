"""Client for the Tavily Search API (live web evidence)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from .cache import TTLCache
from .config import Settings, get_settings
from .sources import (
    compute_days_old,
    detect_prompt_injection,
    extract_domain,
    get_domain_authority_tier,
    is_safe_http_url,
    parse_publication_date,
    sanitize_untrusted_text,
)

logger = logging.getLogger("freshguard.tavily")
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilyError(RuntimeError):
    pass


@dataclass
class SearchResponse:
    query: str
    params: Dict[str, Any]
    answer: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    response_time_ms: int = 0
    cached: bool = False


class TavilyClient:
    def __init__(self, settings: Optional[Settings] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings or get_settings()
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None
        self.cache = TTLCache(maxsize=400, ttl_seconds=max(60, self.settings.cache_ttl_seconds))
        self.calls = 0
        self.failures = 0

    @property
    def configured(self) -> bool:
        return bool(self.settings.tavily_api_key)

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0, transport=self._transport)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def search(
        self,
        query: str,
        *,
        topic: str = "general",
        search_depth: str = "basic",
        max_results: int = 5,
        time_range: Optional[str] = None,
        include_answer: bool = True,
        include_domains: Optional[List[str]] = None,
    ) -> SearchResponse:
        if not self.configured:
            raise TavilyError("TAVILY_API_KEY is not configured")
        q = " ".join((query or "").split())[:380]
        if not q:
            raise TavilyError("empty search query")
        body: Dict[str, Any] = {
            "query": q,
            "topic": topic if topic in ("general", "news", "finance") else "general",
            "search_depth": search_depth if search_depth in ("basic", "advanced", "fast") else "basic",
            "max_results": max(1, min(10, max_results)),
            "include_answer": "basic" if include_answer else False,
            "include_published_date": True,
        }
        if time_range in ("day", "week", "month", "year"):
            body["time_range"] = time_range
        if include_domains:
            body["include_domains"] = include_domains[:20]

        cache_key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached is not None:
            return SearchResponse(**{**cached.__dict__, "cached": True})

        self.calls += 1
        started = time.perf_counter()
        try:
            resp = await self._http().post(
                TAVILY_SEARCH_URL,
                headers={"Authorization": f"Bearer {self.settings.tavily_api_key}", "Content-Type": "application/json"},
                json=body,
            )
        except httpx.HTTPError as exc:
            self.failures += 1
            raise TavilyError(f"Tavily unreachable: {type(exc).__name__}") from exc
        if resp.status_code != 200:
            self.failures += 1
            raise TavilyError(f"Tavily HTTP {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        results: List[Dict[str, Any]] = []
        for item in payload.get("results") or []:
            url = str(item.get("url") or "").strip()
            raw_content = str(item.get("content") or "")
            if not is_safe_http_url(url) or not raw_content.strip():
                continue
            raw_title = str(item.get("title") or extract_domain(url) or "Web source")
            injected = detect_prompt_injection(raw_title) or detect_prompt_injection(raw_content)
            snippet = sanitize_untrusted_text(raw_content, 900)
            dt = parse_publication_date(item.get("published_date"), snippet, url)
            results.append({
                "title": sanitize_untrusted_text(raw_title, 200),
                "url": url,
                "domain": extract_domain(url),
                "snippet": snippet,
                "published_date": dt.strftime("%Y-%m-%d") if dt else None,
                "days_old": compute_days_old(dt),
                "authority_tier": get_domain_authority_tier(url),
                "tavily_score": round(float(item.get("score") or 0.0), 3),
                "injection_suspected": injected,
                "provider": "tavily",
            })
        out = SearchResponse(
            query=q,
            params={k: v for k, v in body.items() if k != "query"},
            answer=sanitize_untrusted_text(str(payload.get("answer") or ""), 600),
            results=results,
            response_time_ms=int((time.perf_counter() - started) * 1000),
        )
        self.cache.set(cache_key, out)
        return out
