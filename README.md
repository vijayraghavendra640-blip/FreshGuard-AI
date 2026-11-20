# 🛡️ FreshGuard AI — Real-Time Stale-Answer Detector for AI Applications

**Geek Room Global AI Hackathon 2026 | Problem Statement 06: Build a Stale-Answer Detector for AI Applications**  
**Powered by Bifrost AI & Tavily Search API**

- 🌐 **Live Working Prototype:** [https://freshguard-ai-26lo.onrender.com/](https://freshguard-ai-26lo.onrender.com/)
- 💻 **Public GitHub Repository:** [https://github.com/vijayraghavendra640-blip/FreshGuard-AI](https://github.com/vijayraghavendra640-blip/FreshGuard-AI)

---

## 📌 1. Project Overview

**FreshGuard AI** is a real-time **Stale-Answer Detector and Live Fact-Verification Engine** built for AI applications.

Large Language Models (LLMs) are trained on static historical snapshots of the web. Because of their knowledge cutoff, they frequently generate **stale, outdated, or hallucinated answers** when asked about **product pricing changes**, **API deprecations and updates**, **evolving government/industry regulations**, leadership changes, and live statistics.

FreshGuard AI sits as an intelligent verification layer on top of LLM outputs. By combining **Bifrost AI** (high-speed LLM gateway and orchestration) with the **Tavily Search API** (real-time web search designed for AI agents), FreshGuard AI:
1. Decomposes AI-generated responses into atomic, verifiable claims.
2. Grounds each claim against live web evidence retrieved via **Tavily API**.
3. Routes every model call (extraction, source vetting, verification, hallucination audit) through a **Bifrost AI gateway**.
4. Computes an **Overall Freshness Score (0–100%)**, classifies every claim as **Verified**, **Needs Review**, or **Stale / Outdated**, and shows the current latest information for each claim with a comparison web URL.

---

## 🚨 2. The Problem

Modern AI applications face a critical reliability gap caused by **temporal decay** and **static training cutoffs**:

1. **Product Pricing Changes:** SaaS platforms, cloud providers, and consumer subscriptions frequently update their pricing tiers and plans, causing LLMs to quote outdated prices and discontinued tiers.
2. **API Deprecations & SDK Updates:** Developer APIs retire legacy endpoints, change rate limits, and release new model versions, leading LLMs to recommend broken or deprecated API calls.
3. **Evolving Regulations & Compliance:** Laws such as the EU AI Act, financial regulations, and data privacy policies transition from proposed bills to active enforcement after an LLM's training cutoff.
4. **Unverified Quantitative Hallucinations:** When an LLM lacks real-time data, it often fabricates plausible-sounding metrics with high confidence and zero source transparency.

---

## 💡 3. Our Solution: FreshGuard AI

FreshGuard AI solves stale AI outputs through an automated **Detect → Search → Verify → Remediate** workflow:

- **Atomic Claim Extraction:** Splits an AI response into individual factual claims and identifies time-sensitive markers (years, dates, `"current"`, `"currently"`, `"latest"`, prices, API versions, and regulatory states).
- **Real-Time Web Grounding (Tavily API):** Queries live authoritative web sources for each extracted claim to retrieve the latest real-world facts.
- **Gateway-Orchestrated Semantic Verification (Bifrost AI):** Routes structured verification prompts through **Bifrost AI** to compare the original AI claim against live Tavily web evidence.
- **Three-Tier Freshness Verdict & Scoring (`0–100%`):**
  - 🟢 **Verified (`75% – 100%`):** Claim is confirmed accurate and current by live Tavily web evidence.
  - 🟡 **Needs Review (`50% – 74%`):** Claim lacks sufficient independent live corroboration or contains unverified claims.
  - 🔴 **Stale / Outdated (`0% – 49%`):** Claim is contradicted by newer pricing, updated API documentation, enacted regulations, or current dates.
- **Current Information with Sources:** Shows what live sources say today for each claim, with a comparison web URL the user can open to verify it.

---

## 🤝 4. How Tavily and Bifrost Work Together

### 🌐 Tavily: live evidence
- Every claim gets a planned Tavily search (`topic` = `news` for leadership, regulation and events; `search_depth` = `advanced` for time-sensitive claims; `include_answer` and `include_published_date` on).
- Results come back with publication dates, which drive the **recency** part of each freshness score.
- If evidence is thin, the Evidence Agent refines the query and searches again.

### ⚡ Bifrost: every model call
- FreshGuard talks only to a **Bifrost AI gateway** (`BIFROST_BASE_URL`, OpenAI-compatible). Bifrost holds the provider key (Groq) and handles retries and **model fallbacks** (`fallbacks` chain in each request).
- These all go through Bifrost: claim extraction, source vetting, verification and the hallucination audit (on a *different* model).
- If the gateway is down or rate-limited, claims are marked **Needs Review**. FreshGuard never falls back to "Verified".

### 🤖 Agentic verification layer
| Agent | What it does |
| :--- | :--- |
| **Claim extractor** | LLM splits the answer into self-contained claims, labels category and time-sensitivity. Claims that add words or numbers not in the answer are rejected and extraction is re-run. |
| **Evidence Agent** | Searches Tavily, screens out prompt-injection snippets, low-credibility domains and duplicates, asks an LLM to vet each source's relevance and reliability, overrides "relevant" judgements on snippets that don't mention the claim's subject, and re-searches when evidence is insufficient. Only vetted sources reach the verifier or the UI. |
| **Verifier Agent** | Judges the claim against vetted sources only, and must cite one source and quote it verbatim. |
| **Hallucination Auditor** | Deterministic checks: the cited source exists, the quote is really in it, and the numbers are in the evidence. Then an independent LLM audit on a different model. A failed audit **sends the claim back to the verifier with the issues listed** (up to 3 attempts). If it still fails, the verdict is withheld as Needs Review. |

---

## 🏗️ 5. Architecture

    React UI (frontend/, built into static/)  --SSE-->  FastAPI (main.py)
                                                           |
                               freshguard/pipeline.py (orchestrator, deadlines, cache)
           +--------------------+--------------------+--------------------+------------------+
       claims.py          Evidence Agent        Verifier Agent     Hallucination Auditor   scoring.py
     (extraction)        (search + vetting)                         (different model)      (evidence-based)
           |                 |        |               |                     |
           +---- bifrost_client.py <--+---------------+---------------------+
                       |              tavily_client.py
                       v                     v
              Bifrost gateway (:8080)   Tavily Search API
                       v
                  Groq models

**Scoring.** Each claim's evidence strength (0–100) is built from source authority (30), recency (25), corroboration (20) and grounding (25: quote verified plus audit result). The freshness score sits inside the verdict's band, so the label and the number always agree:
- 🟢 **Verified** 75–100
- 🟡 **Needs Review** 50–74
- 🔴 **Stale / Outdated** 0–49

The overall verdict is driven by the worst claim: any stale claim makes the report stale. Text with no claims gets no score.

---

## 🛠️ 6. Technologies Used

| Layer | Technology |
| :--- | :--- |
| AI gateway | **Bifrost** (local, `scripts/run_bifrost.py`, config in `bifrost/config.json`) |
| Live web search | **Tavily Search API** |
| Models (via Bifrost) | Groq `openai/gpt-oss-120b` (verifier), `qwen/qwen3.8-27b` (auditor), `openai/gpt-oss-20b` (fallback) |
| Backend | Python 3.13, FastAPI, httpx, Server-Sent Events streaming |
| Frontend | React 19 + TypeScript + Vite, styled on the free shadcn/ui design system with Inter (self-hosted) |
| Tests | pytest with mocked Bifrost and Tavily transports |

---

## 📂 7. Project Structure

    FreshGuard-AI/
    ├── main.py                 # FastAPI app: REST + streaming endpoints, security headers, rate limit
    ├── engine.py               # Backwards-compatible wrapper around the freshguard package
    ├── freshguard/             # Verification engine
    │   ├── config.py           # Settings (env loaded once, platform variables win)
    │   ├── bifrost_client.py   # Bifrost gateway client (fallbacks, 429 back-off, JSON repair)
    │   ├── tavily_client.py    # Tavily client (dates, authority tiers, injection screening, cache)
    │   ├── claims.py           # Claim extraction with grounding check
    │   ├── agents.py           # Evidence Agent, Verifier Agent, Hallucination Auditor
    │   ├── scoring.py          # Evidence-based scoring and aggregation
    │   ├── pipeline.py         # Orchestration, deadlines, streaming events
    │   └── sources.py, cache.py, presets.py
    ├── frontend/               # React app (npm run build -> static/)
    ├── static/                 # Built frontend served by FastAPI
    ├── bifrost/config.json     # Bifrost provider config (keys come from env)
    ├── scripts/run_bifrost.py  # Starts the local Bifrost gateway
    └── tests/                  # pytest suite

---

## 🚀 8. Local Setup

**Prerequisites:** Python 3.10+ (tested on 3.13), Node.js 18+, a Tavily key and a Groq key.

1. Install backend dependencies:

        py -3.13 -m pip install -r requirements-dev.txt

2. Create `.env` from `.env.example` and fill in `TAVILY_API_KEY` and `GROQ_API_KEY`.

3. Start the Bifrost gateway in its own terminal. The first run downloads the Bifrost binary.

        py -3.13 scripts/run_bifrost.py

   The Bifrost dashboard is at http://127.0.0.1:8080.

4. Build the frontend once, or after UI changes:

        cd frontend
        npm install
        npm run build

5. Start FreshGuard:

        py -3.13 -m uvicorn main:app --port 8005

   Then open **http://127.0.0.1:8005**. For UI development with hot reload, run `npm run dev` in `frontend/` and open http://localhost:5173.

6. Run the tests:

        py -3.13 -m pytest

### API
| Method | Path | Purpose |
| :--- | :--- | :--- |
| POST | `/api/verify` · `/api/verify/stream` | Verify an AI answer (JSON report, or live SSE events) |
| POST | `/api/guardrail` | CI/CD gate: `ALLOW_DEPLOY` only if every claim is verified and audited |
| GET | `/api/health` | Gateway reachability, models, Tavily status |
| GET | `/api/presets` | Demo inputs |

> **Note:** Groq's on-demand tier limits tokens per minute per model. FreshGuard spreads load across three models, caps concurrent calls, and waits out 429s using Groq's retry hint. Long answers can still take a minute or two on the free tier.

---

## 🧪 9. Working Prototype & Industry Test Cases

Try the live prototype at **[https://freshguard-ai-26lo.onrender.com/](https://freshguard-ai-26lo.onrender.com/)** across the core domains where LLM answers become stale:

### 💰 Domain 1: Product Pricing Changes
- **Test Case 1 (Stale AI Tier Pricing — `Stale / Outdated`):**
  - **Input:** `OpenAI's highest paid consumer subscription tier for ChatGPT is currently ChatGPT Plus at $20 per month, and there is no $200 per month tier.`
  - **Expected Output:** Flagged as **Stale / Outdated**, noting the launch of **ChatGPT Pro at $200/month**.

### 🔌 Domain 2: APIs & Developer Ecosystem Changes
- **Test Case 2 (Deprecated API Model — `Stale / Outdated`):**
  - **Input:** `OpenAI's recommended flagship model for production API applications is currently text-davinci-003 via the legacy Completions endpoint.`
  - **Expected Output:** Flagged as **Stale / Outdated**, identifying that `text-davinci-003` and the legacy Completions endpoint were deprecated and replaced by newer GPT-4o / GPT-4.1 Chat Completions APIs.
- **Test Case 3 (Current API Endpoint — `Verified`):**
  - **Input:** `Tavily provides a dedicated Search API endpoint at https://api.tavily.com/search designed for AI agents and RAG applications.`
  - **Expected Output:** Confirmed as **Verified** with high freshness confidence and live API documentation link.

### ⚖️ Domain 3: Regulations & Policy Updates
- **Test Case 4 (Outdated AI Regulation Status — `Stale / Outdated`):**
  - **Input:** `The European Union AI Act is currently only a proposed draft bill and has not yet entered into force in the European Union.`
  - **Expected Output:** Flagged as **Stale / Outdated**, explaining that the **EU AI Act officially entered into force on August 1, 2024** with phased compliance deadlines active in 2025–2026.

### 🕒 Domain 4: Temporal Drift & Unverified Claims
- **Test Case 5 (Stale Year / Leadership — `Stale / Outdated`):**
  - **Input:** `The current year is 2024.` / `The current President of the United States is Joe Biden.`
  - **Expected Output:** Flagged as **Stale / Outdated** with updated `2026` calendar and current officeholder facts.



## 👤 Author

**Vijay Raghavendra**  
GitHub: [@vijayraghavendra640-blip](https://github.com/vijayraghavendra640-blip)