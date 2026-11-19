"""Central configuration for FreshGuard AI.

Environment variables are read once. A local `.env` file is loaded with
override=False, so variables set by the deployment platform always win.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_BIFROST_URL = "http://127.0.0.1:8080/v1"
DEFAULT_PRIMARY_MODEL = "groq/openai/gpt-oss-120b"
DEFAULT_FALLBACK_MODELS = "groq/qwen/qwen3.8-27b,groq/openai/gpt-oss-20b"
DEFAULT_AUDITOR_MODEL = "groq/qwen/qwen3.8-27b"
DEFAULT_AUDITOR_FALLBACKS = "groq/openai/gpt-oss-20b,groq/openai/gpt-oss-120b"


def _csv(value: str) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _clean(value: Optional[str]) -> str:
    return (value or "").strip().strip('"').strip("'")


@dataclass(frozen=True)
class Settings:
    tavily_api_key: str
    bifrost_base_url: str
    bifrost_api_key: str
    primary_model: str
    fallback_models: List[str] = field(default_factory=list)
    auditor_model: str = DEFAULT_AUDITOR_MODEL
    auditor_fallbacks: List[str] = field(default_factory=list)
    max_claims: int = 12
    max_sources_per_claim: int = 5
    max_verification_attempts: int = 3
    claim_concurrency: int = 3
    llm_concurrency: int = 3
    rate_limit_retries: int = 3
    rate_limit_max_wait_seconds: float = 30.0
    reasoning_effort: str = "low"
    llm_timeout_seconds: float = 60.0
    claim_timeout_seconds: float = 150.0
    analysis_timeout_seconds: float = 240.0
    cache_ttl_seconds: int = 900
    admin_api_token: str = ""
    guardrail_api_key: str = ""
    rate_limit_per_minute: int = 30
    allowed_origins: List[str] = field(default_factory=list)

    @property
    def bifrost_chat_url(self) -> str:
        base = self.bifrost_base_url.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    @property
    def bifrost_root_url(self) -> str:
        parsed = urlparse(self.bifrost_base_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def bifrost_looks_direct_provider(self) -> bool:
        """True when BIFROST_BASE_URL points straight at a model provider instead of a Bifrost gateway."""
        host = (urlparse(self.bifrost_base_url).netloc or "").lower()
        return any(h in host for h in ("api.groq.com", "api.openai.com", "api.anthropic.com"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env", override=False)
    return Settings(
        tavily_api_key=_clean(os.getenv("TAVILY_API_KEY")),
        bifrost_base_url=_clean(os.getenv("BIFROST_BASE_URL")) or DEFAULT_BIFROST_URL,
        bifrost_api_key=_clean(os.getenv("BIFROST_API_KEY")),
        primary_model=_clean(os.getenv("BIFROST_PRIMARY_MODEL")) or DEFAULT_PRIMARY_MODEL,
        fallback_models=_csv(os.getenv("BIFROST_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS)),
        auditor_model=_clean(os.getenv("BIFROST_AUDITOR_MODEL")) or DEFAULT_AUDITOR_MODEL,
        auditor_fallbacks=_csv(os.getenv("BIFROST_AUDITOR_FALLBACKS", DEFAULT_AUDITOR_FALLBACKS)),
        max_claims=max(1, min(25, _int("MAX_CLAIMS", 12))),
        max_sources_per_claim=max(2, min(10, _int("MAX_SOURCES_PER_CLAIM", 5))),
        max_verification_attempts=max(1, min(5, _int("MAX_VERIFICATION_ATTEMPTS", 3))),
        claim_concurrency=max(1, min(8, _int("CLAIM_CONCURRENCY", 3))),
        llm_concurrency=max(1, min(16, _int("LLM_CONCURRENCY", 3))),
        rate_limit_retries=max(0, min(6, _int("RATE_LIMIT_RETRIES", 3))),
        rate_limit_max_wait_seconds=_float("RATE_LIMIT_MAX_WAIT_SECONDS", 30.0),
        reasoning_effort=_clean(os.getenv("BIFROST_REASONING_EFFORT", "low")).lower(),
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 60.0),
        claim_timeout_seconds=_float("CLAIM_TIMEOUT_SECONDS", 150.0),
        analysis_timeout_seconds=_float("ANALYSIS_TIMEOUT_SECONDS", 240.0),
        cache_ttl_seconds=_int("CACHE_TTL_SECONDS", 900),
        admin_api_token=_clean(os.getenv("ADMIN_API_TOKEN")),
        guardrail_api_key=_clean(os.getenv("GUARDRAIL_API_KEY")),
        rate_limit_per_minute=max(1, _int("RATE_LIMIT_PER_MINUTE", 30)),
        allowed_origins=_csv(os.getenv("ALLOWED_ORIGINS", "http://localhost:8005,http://127.0.0.1:8005,http://localhost:5173,http://127.0.0.1:5173")),
    )
