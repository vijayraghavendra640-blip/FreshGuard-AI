import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine import (
    CLAIM_CACHE,
    DEMO_PRESETS,
    analyze_text_freshness,
    generate_ai_answer_with_bifrost,
)

app = FastAPI(
    title="FreshGuard AI — Stale-Answer Detector",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


class VerifyRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=8000)


class GenerateAndVerifyRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)


class GuardrailRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=8000)
    min_score_threshold: int = Field(default=80, ge=0, le=100)


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/api/presets")
async def get_presets():
    return {"presets": DEMO_PRESETS}


@app.post("/api/verify")
async def verify_endpoint(req: VerifyRequest):
    cleaned = req.text.strip()
    if len(cleaned) < 5:
        raise HTTPException(
            status_code=400,
            detail="Please paste at least one complete statement to verify.",
        )
    return await analyze_text_freshness(cleaned)


@app.post("/api/generate-and-verify")
async def generate_and_verify_endpoint(req: GenerateAndVerifyRequest):
    cleaned_prompt = req.prompt.strip()
    if len(cleaned_prompt) < 3:
        raise HTTPException(status_code=400, detail="Please enter a valid question.")
    gen_data = await generate_ai_answer_with_bifrost(cleaned_prompt)
    generated_answer = gen_data.get("answer", "")
    audit_report = await analyze_text_freshness(generated_answer)
    audit_report["generated_response"] = generated_answer
    audit_report["generation_model"] = gen_data.get("model_used", "Bifrost -> Groq")
    return audit_report


@app.post("/api/guardrail")
async def cicd_guardrail_endpoint(req: GuardrailRequest):
    report = await analyze_text_freshness(req.text.strip())
    score = report.get("overall_freshness_score", 0)
    passed = score >= req.min_score_threshold and report.get("stale_count", 0) == 0
    return {
        "guardrail_passed": passed,
        "action": "ALLOW_DEPLOY" if passed else "BLOCK_STALE_OUTPUT",
        "threshold": req.min_score_threshold,
        "overall_freshness_score": score,
        "stale_count": report.get("stale_count", 0),
        "report": report,
    }


@app.post("/api/cache/clear")
async def clear_cache():
    count = len(CLAIM_CACHE)
    CLAIM_CACHE.clear()
    return {"status": "cleared", "entries_removed": count}