# 🛡️ FreshGuard AI — Real-Time Stale-Answer Detector for AI Applications

**Geek Room Global AI Hackathon 2026 | Problem Statement 06: Build a Stale-Answer Detector for AI Applications**  
**Powered by Bifrost AI & Tavily Search API**

- 🌐 **Live Working Prototype:** [https://freshguard-ai-9tgb.onrender.com/](https://freshguard-ai-9tgb.onrender.com/)
- 💻 **Public GitHub Repository:** [https://github.com/vijayraghavendra640-blip/FreshGuard-AI](https://github.com/vijayraghavendra640-blip/FreshGuard-AI)

---

## 📌 1. Project Overview

**FreshGuard AI** is a real-time **Stale-Answer Detector and Live Fact-Verification Engine** built for AI applications.

Large Language Models (LLMs) are trained on static historical snapshots of the web. Because of their knowledge cutoff, they frequently generate **stale, outdated, or hallucinated answers** when asked about **product pricing changes**, **API deprecations and updates**, **evolving government/industry regulations**, leadership changes, and live statistics.

FreshGuard AI sits as an intelligent verification layer on top of LLM outputs. By combining **Bifrost AI** (high-speed LLM gateway and orchestration) with the **Tavily Search API** (real-time web search designed for AI agents), FreshGuard AI:
1. Decomposes AI-generated responses into atomic, verifiable claims.
2. Grounds each claim against live web evidence retrieved via **Tavily API**.
3. Routes claim-vs-evidence verification and auto-correction prompts through **Bifrost AI** to `llama-3.3-70b-versatile`.
4. Computes an **Overall Freshness Score (0–100%)**, classifies every claim as **Verified**, **Needs Review**, or **Stale / Outdated**, and provides an up-to-date corrected answer with clickable live web citations.

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
- **Automated Answer Correction:** Generates a clean, up-to-date replacement statement alongside the live source URL.

---

## 🤝 4. How Both Combined Technologies Contribute (`Bifrost AI` + `Tavily API`)

FreshGuard AI is built by combining **Bifrost AI** and **Tavily Search API** into a unified verification pipeline. Each technology solves half of the stale-answer challenge:

### ⚡ 1. How Bifrost AI Contributes to FreshGuard AI
**Bifrost AI** serves as the **Unified AI Gateway & LLM Orchestration Layer** in our backend (`engine.py`):
- **High-Speed Unified LLM Routing:** Routes FreshGuard AI's claim decomposition, semantic contradiction analysis, and answer-rewriting requests through an OpenAI-compatible gateway endpoint (`BIFROST_BASE_URL` / Groq `llama-3.3-70b-versatile`) with microsecond gateway overhead.
- **Resilience & Automatic Failover:** Ensures that if an LLM inference call experiences rate limits or transient timeouts during multi-claim verification, requests are handled gracefully with fallback protection so the verification pipeline never crashes.
- **Structured Verification Output:** Powers the semantic reasoning step that compares the user's AI text against live search context and outputs structured JSON verdicts (`Verified`, `Needs Review`, `Stale / Outdated`), confidence scores, and natural-language corrections.

### 🌐 2. How Tavily Search API Contributes to FreshGuard AI
**Tavily API** (`https://api.tavily.com/search`) serves as the **Real-Time Web Intelligence & Grounding Layer**:
- **Purpose-Built Search for AI Verification:** Unlike traditional search engines that return raw HTML clutter, Tavily returns clean, high-signal factual snippets, synthesized context, and authoritative URLs ready for LLM consumption.
- **Eliminating Knowledge Cutoff Blindness:** For every claim extracted from the AI output, Tavily fetches the current real-world state from the live internet—whether it is a current subscription price, live API changelog, or newly enacted law.
- **Auditable Citation Links:** Supplies the direct live web URLs displayed on each verification card in the FreshGuard AI dashboard.

### 🔗 Synergy: Why Combining Bifrost AI + Tavily API Matters
- **Tavily API alone** can fetch live web snippets, but cannot semantically decompose complex paragraphs, reason over subtle temporal contradictions, or rewrite stale sentences into corrected prose.
- **Bifrost AI + LLM inference alone** can reason over text rapidly, but without live web grounding it remains trapped inside the model's static training cutoff.
- **Together in FreshGuard AI:** **Tavily API** supplies real-time factual truth from the live web, and **Bifrost AI** orchestrates ultra-fast, reliable LLM reasoning over that live evidence to detect staleness and auto-correct answers in real time.

---

## 🏗️ 5. Technical Architecture & Implementation

### System Architecture Diagram

    +------------------------------------------------------------------------+
    |                        USER / AI APPLICATION                           |
    |          Submits AI-Generated Answer (+ Optional Question)             |
    +-----------------------------------+------------------------------------+
                                        |
                                        v
    +------------------------------------------------------------------------+
    |                  FASTAPI BACKEND SERVER (main.py)                      |
    |            REST Endpoints: POST /verify  |  GET /health                |
    +-----------------------------------+------------------------------------+
                                        |
                                        v
    +------------------------------------------------------------------------+
    |           STEP 1: CLAIM DECOMPOSITION & TEMPORAL ANALYSIS              |
    |  - Splits AI output into atomic verifiable claims (engine.py)          |
    |  - Detects temporal markers (years, prices, APIs, regulations)         |
    +-----------------------------------+------------------------------------+
                                        |
                                        v
    +------------------------------------------------------------------------+
    |           STEP 2: REAL-TIME WEB GROUNDING (TAVILY SEARCH API)          |
    |  - Sends targeted search queries to https://api.tavily.com/search      |
    |  - Retrieves live factual snippets, answers, and source URLs           |
    +-----------------------------------+------------------------------------+
                                        |
                                        v
    +------------------------------------------------------------------------+
    |        STEP 3: SEMANTIC VERIFICATION GATEWAY (BIFROST AI + GROQ)       |
    |  - Routes Claim + Live Tavily Evidence through Bifrost AI Gateway      |
    |  - Evaluates temporal drift, factual contradictions & evidence support |
    |  - Generates updated factual correction for any Stale/Outdated claim   |
    +-----------------------------------+------------------------------------+
                                        |
                                        v
    +------------------------------------------------------------------------+
    |        STEP 4: FRESHNESS SCORING & INTERACTIVE DASHBOARD UI            |
    |  - Computes Overall Freshness Score (0-100%) & Status Badge            |
    |  - Displays Verified, Needs Review & Stale counts + Live Web URLs      |
    +-----------------------------------+------------------------------------+

### Core Implementation Modules
1. **`main.py` (FastAPI Application & Routing Layer):**
   - Serves the web dashboard (`GET /`) and exposes the verification REST API (`POST /verify`, `POST /api/verify`, and `GET /health`).
   - Validates incoming payloads using Pydantic models and returns structured JSON responses to the frontend.
2. **`engine.py` (FreshGuard Verification Engine):**
   - **Claim Extraction & Temporal Drift Engine:** Parses input text into atomic claims and checks time-anchored statements against the current calendar year (`2026`) and live facts.
   - **Tavily Search Client:** Queries the Tavily API (`https://api.tavily.com/search`) with `search_depth` and `include_answer` enabled to gather live web evidence and source URLs.
   - **Bifrost AI Gateway Integration:** Routes LLM verification requests through the Bifrost-compatible chat completions layer (`BIFROST_BASE_URL` / Groq `llama-3.3-70b-versatile`) to compare claims against Tavily evidence and synthesize corrected statements.
   - **Freshness Score Aggregator:** Calculates per-claim scores and aggregates them into an overall freshness percentage (`0–100%`) and overall status (`Verified`, `Needs Review`, or `Stale / Outdated`).
3. **`static/index.html` (Interactive Frontend Dashboard):**
   - Clean, responsive dashboard displaying the **Overall Freshness Score** gauge, summary counters (**Verified Information**, **Needs Review**, **Stale / Outdated**), and per-claim verification cards with **Current Latest Information** and clickable **Live Web URLs**.

---

## 🛠️ 6. Technologies Used

| Layer | Technology | Role in Project |
| :--- | :--- | :--- |
| **AI Gateway & Routing** | **Bifrost AI** | Unified LLM gateway for low-latency model routing, resilience, and structured verification requests |
| **Live Web Search** | **Tavily Search API** | Real-time web search and factual grounding for AI claims |
| **LLM Inference** | **Groq Cloud (`llama-3.3-70b-versatile`)** | High-speed semantic claim verification and stale-answer rewriting |
| **Backend Framework** | **Python 3.13, FastAPI, Uvicorn** | Asynchronous REST API server and backend orchestration |
| **HTTP & Environment** | **`httpx`, `python-dotenv`, `pydantic`** | API requests, environment variable security, and schema validation |
| **Frontend Interface** | **HTML5, CSS3, Vanilla JavaScript** | Interactive real-time Freshness Detection & Live Verification UI |
| **Deployment** | **Render Cloud, Git & GitHub** | Public cloud hosting and version control |

---

## 📂 7. Project Folder Structure

    FreshGuard-AI/
    ├── main.py              # FastAPI server entry point & REST API endpoints
    ├── engine.py            # Core Stale-Answer Detection, Bifrost AI & Tavily API integration
    ├── requirements.txt     # Python package dependencies
    ├── .gitignore           # Excludes .env secrets and local environment files
    ├── README.md            # Project documentation
    └── static/
        └── index.html       # FreshGuard AI Interactive Web Dashboard

---

## 🚀 8. Installation & Local Setup Steps

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- A **Tavily API Key** (`tvly-...`)
- A **Groq / Bifrost AI API Key** (`gsk_...`)

### Step 1: Clone the Repository

    git clone https://github.com/vijayraghavendra640-blip/FreshGuard-AI.git
    cd FreshGuard-AI

### Step 2: Install Dependencies

    pip install -r requirements.txt

*(Or on Windows using Python 3.13):*

    py -3.13 -m pip install fastapi uvicorn httpx python-dotenv pydantic

### Step 3: Set Up Environment Variables (`.env`)
Create a `.env` file in the project root folder:

    GROQ_API_KEY=your_groq_api_key_here
    TAVILY_API_KEY=your_tavily_api_key_here
    BIFROST_BASE_URL=https://api.groq.com/openai/v1

### Step 4: Run the Application Server

    uvicorn main:app --reload --port 8005

*(Or on Windows with Python 3.13):*

    py -3.13 -m uvicorn main:app --reload --port 8005

### Step 5: Launch the Dashboard
Open your browser and navigate to:

    http://127.0.0.1:8005

---

## 🧪 9. Working Prototype & Industry Test Cases

Try the live prototype at **[https://freshguard-ai-9tgb.onrender.com/](https://freshguard-ai-9tgb.onrender.com/)** across the core domains where LLM answers become stale:

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