import asyncio
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Deque, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from freshguard import ENGINE_VERSION
from freshguard.config import get_settings
from freshguard.pipeline import get_engine
from freshguard.presets import DEMO_PRESETS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("freshguard.api")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()
    health = await engine.gateway.health()
    if not health.get("reachable"):
        logger.warning("Bifrost gateway is not reachable at %s; claims will be marked Needs Review until it is.", settings.bifrost_base_url)
    if settings.bifrost_looks_direct_provider:
        logger.warning("BIFROST_BASE_URL points at a model provider, not a Bifrost gateway.")
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY is not set; live evidence retrieval is disabled.")
    yield
    await engine.aclose()


app = FastAPI(title="FreshGuard AI: Stale-Answer Detector", version=ENGINE_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token", "X-API-Key"],
)

RATE_LIMIT_WINDOW = 60.0
_request_log: Dict[str, Deque[float]] = defaultdict(deque)
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def _client_ip(request: Request) -> str:
    # Run uvicorn with --proxy-headers behind a reverse proxy so request.client is the real client.
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        ip = _client_ip(request)
        now = time.monotonic()
        bucket = _request_log[ip]
        while bucket and (now - bucket[0]) > RATE_LIMIT_WINDOW:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again in a minute."})
        bucket.append(now)
        if len(_request_log) > 5000:  # prune idle clients
            for k in [k for k, v in _request_log.items() if not v or (now - v[-1]) > RATE_LIMIT_WINDOW]:
                _request_log.pop(k, None)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        response.headers["Content-Security-Policy"] = CSP
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)


class GuardrailRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    min_score_threshold: int = Field(default=80, ge=0, le=100)


def _clean_or_422(value: str, what: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail=f"{what} cannot be empty.")
    return cleaned


def _sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _stream_job(request: Request, job) -> AsyncIterator[str]:
    """Run `job(emit)` and stream every emitted event as Server-Sent Events."""
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(evt: Dict[str, Any]) -> None:
        await queue.put(evt)

    async def runner() -> None:
        try:
            await job(emit)
        except HTTPException as exc:
            await queue.put({"type": "error", "status": exc.status_code, "detail": exc.detail})
        except Exception:
            logger.exception("streamed job failed")
            await queue.put({"type": "error", "status": 500, "detail": "Verification failed unexpectedly."})
        finally:
            await queue.put({"type": "done"})

    task = asyncio.create_task(runner())
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
                continue
            yield _sse(evt)
            if evt.get("type") == "done":
                break
    finally:
        if not task.done():
            task.cancel()


SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


# ------------------------------------------------------------------ API

@app.get("/health")
@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    engine = get_engine()
    gateway = await engine.gateway.health()
    ready = bool(gateway.get("reachable")) and engine.tavily.configured and not settings.bifrost_looks_direct_provider
    return {
        "status": "ok" if ready else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "tavily_configured": engine.tavily.configured,
        "bifrost": gateway,
        "gateway_stats": engine.gateway.stats.as_dict(),
        "tavily_stats": {"calls": engine.tavily.calls, "failures": engine.tavily.failures},
        "cache_entries": engine.claim_cache.size(),
        "limits": {"max_claims": settings.max_claims, "max_verification_attempts": settings.max_verification_attempts},
    }


@app.get("/api/presets")
async def get_presets():
    return {"presets": DEMO_PRESETS}


@app.post("/api/verify")
@app.post("/api/analyze")
async def verify_text_endpoint(req: VerifyRequest):
    return await get_engine().analyze(_clean_or_422(req.text, "Input text"))


@app.post("/api/verify/stream")
async def verify_text_stream(req: VerifyRequest, request: Request):
    text = _clean_or_422(req.text, "Input text")
    return StreamingResponse(_stream_job(request, lambda emit: get_engine().analyze(text, emit)),
                             media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/api/guardrail")
async def cicd_guardrail_endpoint(req: GuardrailRequest, x_api_key: Optional[str] = Header(default=None)):
    if settings.guardrail_api_key and not (x_api_key and secrets.compare_digest(x_api_key, settings.guardrail_api_key)):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
    report = await get_engine().analyze(_clean_or_422(req.text, "Input text"))
    claims = report.get("claims", [])
    total = int(report.get("total_claims") or 0)
    score = report.get("overall_score")
    all_grounded = all(c.get("audit", {}).get("status") == "passed" for c in claims)
    passed = (
        total > 0 and report.get("overall_verdict") == "Verified" and report.get("verified_count") == total
        and all_grounded and score is not None and score >= req.min_score_threshold
    )
    if passed:
        reason = "All claims verified against vetted live sources and passed the hallucination audit."
    elif total == 0:
        reason = "No verifiable claims found."
    elif report.get("stale_count"):
        reason = f"{report['stale_count']} claim(s) are stale or outdated."
    elif report.get("needs_review_count"):
        reason = f"{report['needs_review_count']} claim(s) could not be verified."
    elif not all_grounded:
        reason = "Some verdicts were not confirmed by the independent auditor."
    else:
        reason = f"Score {score} is below the threshold {req.min_score_threshold}."
    return {
        "guardrail_passed": passed, "action": "ALLOW_DEPLOY" if passed else "BLOCK_DEPLOY", "reason": reason,
        "overall_score": score, "overall_verdict": report.get("overall_verdict"),
        "min_score_threshold": req.min_score_threshold, "total_claims": total,
        "stale_count": report.get("stale_count"), "needs_review_count": report.get("needs_review_count"),
        "verified_count": report.get("verified_count"), "report": report,
    }


@app.post("/api/cache/clear")
async def clear_cache_endpoint(x_admin_token: Optional[str] = Header(default=None)):
    if not settings.admin_api_token:
        raise HTTPException(status_code=403, detail="Cache clearing is disabled. Set ADMIN_API_TOKEN to enable it.")
    if not (x_admin_token and secrets.compare_digest(x_admin_token, settings.admin_api_token)):
        raise HTTPException(status_code=403, detail="Invalid X-Admin-Token header.")
    engine = get_engine()
    cleared = engine.claim_cache.clear() + engine.tavily.cache.clear()
    return {"status": "cleared", "entries_cleared": cleared}


# ------------------------------------------------------------------ frontend (React build in ./static)

if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not built. Run `npm run build` in ./frontend.")
    return FileResponse(str(index_file))


@app.get("/{asset_name}")
async def serve_root_asset(asset_name: str):
    """Serve top-level build files such as favicon.svg; anything else falls back to 404."""
    candidate = (STATIC_DIR / asset_name).resolve()
    if candidate.parent == STATIC_DIR.resolve() and candidate.is_file() and candidate.suffix in (".svg", ".ico", ".png", ".txt", ".webmanifest"):
        return FileResponse(str(candidate))
    raise HTTPException(status_code=404, detail="Not found")
