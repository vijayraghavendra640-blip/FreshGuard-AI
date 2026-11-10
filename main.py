import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import (
    CLAIM_CACHE,
    DEMO_PRESETS,
    analyze_text_freshness,
    generate_ai_answer_with_bifrost,
    get_llm_api_key,
    get_tavily_api_key,
)

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="FreshGuard AI — Stale-Answer Detector & Live Fact Verification", version="2.0.0")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:8005,http://127.0.0.1:8005")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
_request_log: Dict[str, Deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        client_ip = request.client.host if request.client else "local"
        now = time.monotonic()
        bucket = _request_log[client_ip]
        while bucket and (now - bucket[0]) > RATE_LIMIT_WINDOW:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
        bucket.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


class GenerateAndVerifyRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class GuardrailRequest(BaseModel):
    text: str = Field(..., max_length=8000)
    min_score_threshold: int = Field(default=80, ge=0, le=100)


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(str(index_file))


@app.get("/health")
@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tavily_configured": bool(get_tavily_api_key()),
        "llm_configured": bool(get_llm_api_key()),
        "cache_entries": CLAIM_CACHE.size(),
    }


@app.get("/api/presets")
async def get_presets():
    return {"presets": DEMO_PRESETS}


@app.post("/api/verify")
@app.post("/api/analyze")
async def verify_text_endpoint(req: VerifyRequest):
    cleaned = req.text.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Input text cannot be empty.")
    return await analyze_text_freshness(cleaned)


@app.post("/api/generate-and-verify")
async def generate_and_verify_endpoint(req: GenerateAndVerifyRequest):
    cleaned_prompt = req.prompt.strip()
    if not cleaned_prompt:
        raise HTTPException(status_code=422, detail="Prompt cannot be empty.")
    gen_result = await generate_ai_answer_with_bifrost(cleaned_prompt)
    if isinstance(gen_result, dict):
        generated_text = str(gen_result.get("generated_text") or gen_result.get("answer") or gen_result.get("response") or "").strip()
        gen_ok = bool(gen_result.get("ok", True))
        model_used = str(gen_result.get("model", "unknown"))
        provider_used = str(gen_result.get("provider", "bifrost"))
    else:
        generated_text = str(gen_result).strip()
        gen_ok = bool(generated_text)
        model_used = "unknown"
        provider_used = "bifrost"

    if not generated_text or not gen_ok:
        return {
            "prompt": cleaned_prompt, "generated_text": generated_text,
            "generation_succeeded": False, "model": model_used, "provider": provider_used,
            "verification": await analyze_text_freshness(""),
        }
    report = await analyze_text_freshness(generated_text)
    return {
        "prompt": cleaned_prompt, "generated_text": generated_text,
        "generation_succeeded": True, "model": model_used, "provider": provider_used,
        "verification": report, **report,
    }


@app.post("/api/guardrail")
async def cicd_guardrail_endpoint(req: GuardrailRequest):
    cleaned = (req.text or "").strip()
    if not cleaned:
        return {
            "guardrail_passed": False, "action": "BLOCK_DEPLOY",
            "reason": "Empty or whitespace-only text cannot pass guardrail.",
            "overall_score": 0, "min_score_threshold": req.min_score_threshold, "total_claims": 0,
        }
    report = await analyze_text_freshness(cleaned)
    total_claims = int(report.get("total_claims", 0))
    stale_count = int(report.get("stale_count", 0))
    incorrect_count = int(report.get("incorrect_count", 0))
    needs_review_count = int(report.get("needs_review_count", 0))
    verified_count = int(report.get("verified_count", 0))
    score = int(report.get("overall_score", 0))
    overall_verdict = str(report.get("overall_verdict", "Needs Review"))
    threshold = max(1, int(req.min_score_threshold))

    passed = (
        total_claims > 0 and stale_count == 0 and incorrect_count == 0
        and needs_review_count == 0 and verified_count == total_claims
        and overall_verdict == "Verified" and score >= threshold
    )
    return {
        "guardrail_passed": passed,
        "action": "ALLOW_DEPLOY" if passed else "BLOCK_DEPLOY",
        "overall_score": score, "overall_verdict": overall_verdict,
        "min_score_threshold": req.min_score_threshold, "total_claims": total_claims,
        "stale_count": stale_count, "needs_review_count": needs_review_count,
        "verified_count": verified_count, "report": report,
    }


@app.post("/api/cache/clear")
async def clear_cache_endpoint(request: Request, x_admin_token: Optional[str] = Header(default=None)):
    configured_token = os.getenv("ADMIN_API_TOKEN", "").strip()
    client_host = request.client.host if request.client else ""
    if configured_token:
        if x_admin_token != configured_token:
            raise HTTPException(status_code=403, detail="Invalid X-Admin-Token header.")
    elif client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(status_code=403, detail="Restricted to localhost or admin.")
    CLAIM_CACHE.clear()
    return {"status": "cleared", "cache_entries": 0}