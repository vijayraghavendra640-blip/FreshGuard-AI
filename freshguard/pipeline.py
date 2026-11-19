"""FreshGuard verification pipeline.

extract claims (Bifrost) -> for each claim, in parallel with a deadline:
    gather + vet evidence (Tavily + Evidence Agent)
    verify (Verifier Agent) -> audit (Hallucination Auditor) -> re-verify on failure
    score from evidence
-> aggregate into an overall freshness report
Progress events are streamed through an optional `emit` coroutine.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import ENGINE_VERSION
from .agents import (
    EmitFn, EvidenceAgent, EvidenceBundle, GroundingAuditor, Trace, VerifierAgent, verify_with_audit,
)
from .bifrost_client import BifrostClient, BifrostError
from .cache import TTLCache
from .claims import Claim, check_current_year_claim, extract_claims
from .config import Settings, get_settings
from .scoring import LABELS, aggregate, evidence_strength, freshness_score
from .sources import normalize_for_match, quote_in_text
from .tavily_client import TavilyClient

logger = logging.getLogger("freshguard.pipeline")

def _public_source(s: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("id", "title", "url", "domain", "snippet", "published_date", "days_old", "authority_tier", "tavily_score", "provider", "vetting")
    return {k: s.get(k) for k in keys if k in s}


def _rejected_summary(s: Dict[str, Any]) -> Dict[str, Any]:
    return {"title": s.get("title"), "url": s.get("url"), "domain": s.get("domain"),
            "reason": s.get("rejection_reason"), "rejected_by": s.get("rejected_by")}


class FreshGuardEngine:
    def __init__(self, settings: Optional[Settings] = None, gateway: Optional[BifrostClient] = None, tavily: Optional[TavilyClient] = None):
        self.settings = settings or get_settings()
        self.gateway = gateway or BifrostClient(self.settings)
        self.tavily = tavily or TavilyClient(self.settings)
        self.evidence = EvidenceAgent(self.tavily, self.gateway, self.settings)
        self.verifier = VerifierAgent(self.gateway)
        self.auditor = GroundingAuditor(self.gateway, self.settings)
        self.claim_cache = TTLCache(maxsize=500, ttl_seconds=self.settings.cache_ttl_seconds)

    async def aclose(self) -> None:
        await self.gateway.aclose()
        await self.tavily.aclose()

    # ---------------------------------------------------------------- claims
    def _base_result(self, claim: Claim) -> Dict[str, Any]:
        return {
            "id": claim.id, "claim": claim.text, "source_sentence": claim.source_sentence or claim.text,
            "category": claim.category, "time_sensitive": claim.time_sensitive, "freshness_reason": claim.freshness_reason,
            "verdict": "Needs Review", "freshness_score": 50, "evidence_strength": 0,
            "score_breakdown": {"authority": 0, "recency": 0, "corroboration": 0, "grounding": 0},
            "confidence": 0, "explanation": "", "current_fact": "", "corrected_statement": "", "evidence_quote": "",
            "quote_verified": False, "cited_source": None, "sources": [], "rejected_sources": [], "tavily_answer": "",
            "search_queries": [], "vetting_method": "none", "audit": {"status": "not_run", "issues": []},
            "verification_attempts": 0, "models": {}, "agent_trace": [], "cached": False,
        }

    async def verify_claim(self, claim: Claim, emit: EmitFn = None) -> Dict[str, Any]:
        cache_key = f"{ENGINE_VERSION}:{datetime.now(timezone.utc).date()}:{normalize_for_match(claim.text)}"
        cached = self.claim_cache.get(cache_key)
        if cached is not None:
            return {**cached, "id": claim.id, "cached": True}

        trace = Trace(claim.id, emit)
        result = self._base_result(claim)

        year = check_current_year_claim(claim.text)
        if year is not None:
            ok, claimed, actual = year
            label = "Verified" if ok else "Stale / Outdated"
            result.update({
                "verdict": label, "evidence_strength": 100, "freshness_score": 100 if ok else 0, "confidence": 100,
                "explanation": f"Computed from the system clock: the current year is {actual}.",
                "current_fact": f"The current year is {actual}.",
                "corrected_statement": "" if ok else claim.text.replace(str(claimed), str(actual)),
                "audit": {"status": "passed", "issues": []}, "vetting_method": "computed",
            })
            await trace.add("Temporal Check", "system clock", "ok", f"Claimed {claimed}, actual {actual}")
            result["agent_trace"] = trace.steps
            return result

        bundle: EvidenceBundle = await self.evidence.gather(claim, trace)
        result.update({
            "sources": [_public_source(s) for s in bundle.vetted],
            "rejected_sources": [_rejected_summary(s) for s in bundle.rejected][:12],
            "tavily_answer": bundle.tavily_answer, "search_queries": bundle.queries, "vetting_method": bundle.vetting_method,
        })
        if not bundle.vetted:
            reason = bundle.search_error or (
                "Tavily returned no sources that passed screening and vetting." if bundle.queries else "No live search was performed."
            )
            result["explanation"] = f"Not enough trustworthy live evidence to judge this claim. {reason}"
            await trace.add("Verifier Agent", "skipped", "warn", "No vetted evidence; verdict withheld.")
            result["agent_trace"] = trace.steps
            return result  # not cached: evidence may appear on retry

        outcome = await verify_with_audit(claim, bundle, self.verifier, self.auditor, self.settings.max_verification_attempts, trace)
        d = outcome.decision
        by_id = {s["id"]: s for s in bundle.vetted}
        cited = by_id.get(d.get("cited_source_id") or "") if d["verdict"] != "NEEDS_REVIEW" else None
        supporting = [by_id[i] for i in dict.fromkeys(([cited["id"]] if cited else []) + list(d.get("supporting_source_ids") or [])) if i in by_id]
        quote_ok = bool(cited and quote_in_text(d.get("evidence_quote", ""), cited["snippet"], min_tokens=4))
        label = LABELS[d["verdict"]]
        strength = evidence_strength(d["verdict"], claim.time_sensitive, cited, supporting, quote_ok, outcome.audit_status)
        result.update({
            "verdict": label,
            "evidence_strength": strength["total"],
            "score_breakdown": strength["breakdown"],
            "freshness_score": freshness_score(label, strength["total"]),
            "confidence": d.get("confidence", 0),
            "explanation": d.get("explanation", ""),
            "current_fact": d.get("current_fact", "") if label != "Needs Review" else "",
            "corrected_statement": d.get("corrected_statement", "") if label == "Stale / Outdated" else "",
            "evidence_quote": d.get("evidence_quote", "") if cited else "",
            "quote_verified": quote_ok,
            "cited_source": _public_source(cited) if cited else None,
            "supporting_source_ids": [s["id"] for s in supporting],
            "audit": {"status": outcome.audit_status, "issues": outcome.audit_issues, "withheld": outcome.withheld},
            "verification_attempts": outcome.attempts,
            "models": {"verifier": outcome.verifier_model, "auditor": outcome.auditor_model},
            "agent_trace": trace.steps,
        })
        if not outcome.withheld:
            self.claim_cache.set(cache_key, result)
        return result

    # ---------------------------------------------------------------- analysis
    async def analyze(self, text: str, emit: EmitFn = None) -> Dict[str, Any]:
        started = time.perf_counter()
        text = (text or "").strip()
        tavily_calls_before = self.tavily.calls
        llm_calls_before = self.gateway.stats.calls
        warnings: List[str] = []

        async def send(evt: Dict[str, Any]) -> None:
            if emit:
                try:
                    await emit(evt)
                except Exception:
                    logger.debug("emit failed", exc_info=True)

        if not self.tavily.configured:
            warnings.append("TAVILY_API_KEY is not configured: no live evidence can be retrieved.")
        if self.settings.bifrost_looks_direct_provider:
            warnings.append("BIFROST_BASE_URL points directly at a model provider, not a Bifrost gateway.")

        await send({"type": "stage", "stage": "extracting", "detail": "Identifying factual claims"})
        extraction = await extract_claims(text, self.gateway, self.settings.max_claims)
        if extraction.note:
            warnings.append(extraction.note)
        if extraction.truncated:
            warnings.append(f"Only the first {self.settings.max_claims} claims were checked.")
        claims = extraction.claims
        await send({"type": "claims", "claims": [{"id": c.id, "claim": c.text, "category": c.category, "time_sensitive": c.time_sensitive} for c in claims],
                    "extraction": {"method": extraction.method, "rejected": extraction.rejected, "model": extraction.model}})
        await send({"type": "stage", "stage": "verifying", "detail": f"Verifying {len(claims)} claim(s)"})

        sem = asyncio.Semaphore(self.settings.claim_concurrency)

        async def run_one(c: Claim) -> Dict[str, Any]:
            async with sem:
                try:
                    res = await asyncio.wait_for(self.verify_claim(c, emit), timeout=self.settings.claim_timeout_seconds)
                except asyncio.TimeoutError:
                    res = {**self._base_result(c), "explanation": "Verification timed out before a grounded verdict was reached."}
                except Exception as exc:  # never let one claim break the report
                    logger.exception("claim %s failed", c.id)
                    res = {**self._base_result(c), "explanation": f"Verification failed unexpectedly ({type(exc).__name__})."}
            await send({"type": "claim_result", "claim": res})
            return res

        tasks = [asyncio.create_task(run_one(c)) for c in claims]
        results: List[Dict[str, Any]] = []
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=self.settings.analysis_timeout_seconds)
            for t in pending:
                t.cancel()
            if pending:
                warnings.append("Overall analysis deadline reached; unfinished claims were marked Needs Review.")
            for c, t in zip(claims, tasks):
                if t in done and not t.cancelled() and t.exception() is None:
                    results.append(t.result())
                else:
                    results.append({**self._base_result(c), "explanation": "Verification did not finish before the deadline."})

        agg = aggregate(results)
        time_sensitive = sum(1 for r in results if r["time_sensitive"])
        summary = (
            f"Checked {agg['total_claims']} claim(s), {time_sensitive} time-sensitive: "
            f"{agg['verified_count']} verified, {agg['stale_count']} stale/outdated, {agg['needs_review_count']} need review."
            if results else "No verifiable factual claims were found in the text."
        )
        report = {
            "report_id": uuid.uuid4().hex[:12],
            "analyzed_text": text,
            **agg,
            "freshness_score": agg["overall_score"],
            "incorrect_count": 0,
            "time_sensitive_count": time_sensitive,
            "summary": summary,
            "claims": results,
            "pipeline": {
                "extraction": {"method": extraction.method, "model": extraction.model, "attempts": extraction.attempts,
                               "rejected_claims": extraction.rejected},
                "tavily_searches": self.tavily.calls - tavily_calls_before,
                "bifrost_calls": self.gateway.stats.calls - llm_calls_before,
                "gateway": {"base_url": self.settings.bifrost_base_url, "primary_model": self.settings.primary_model,
                            "fallback_models": self.settings.fallback_models, "auditor_model": self.settings.auditor_model},
            },
            "warnings": warnings,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine_version": ENGINE_VERSION,
        }
        await send({"type": "report", "report": report})
        return report

_ENGINE: Optional[FreshGuardEngine] = None


def get_engine() -> FreshGuardEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = FreshGuardEngine()
    return _ENGINE
