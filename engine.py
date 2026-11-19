"""Backwards-compatible entry point for the FreshGuard engine.

The original 3,500-line engine.py contained many stacked re-definitions of the
same functions; only the last copy of each ran. The reusable pieces (source
credibility tiers, prompt-injection screening, date parsing, quote checks,
TTL cache, presets) now live in the `freshguard` package, which also adds the
Bifrost gateway client, the Tavily client and the agentic verification layer.

This module keeps the old public names working for any existing callers.
"""
from __future__ import annotations

from typing import Any, Dict

from freshguard import ENGINE_VERSION
from freshguard.config import get_settings
from freshguard.pipeline import get_engine
from freshguard.presets import DEMO_PRESETS

__all__ = [
    "ENGINE_VERSION", "DEMO_PRESETS", "CLAIM_CACHE", "analyze_text_freshness",
    "get_llm_api_key", "get_tavily_api_key",
]

CLAIM_CACHE = get_engine().claim_cache


async def analyze_text_freshness(text: Any = "", **kwargs: Any) -> Dict[str, Any]:
    if isinstance(text, dict):
        text = text.get("text") or text.get("answer") or ""
    text = text or kwargs.get("text") or kwargs.get("answer") or ""
    return await get_engine().analyze(str(text))


def get_llm_api_key() -> str:
    """The Bifrost virtual key, if one is configured (provider keys live in Bifrost)."""
    return get_settings().bifrost_api_key


def get_tavily_api_key() -> str:
    return get_settings().tavily_api_key
