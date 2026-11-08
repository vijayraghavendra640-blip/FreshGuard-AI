# 🛡️ FreshGuard AI — Stale-Answer Detector & Live Fact Verification

**Geek Room Global AI Hackathon 2026 • Problem Statement 06 (Tavily)**  
*Theme: AI-Powered Fact Verification & Information Freshness*

---

## 🚀 Overview

Large Language Models (LLMs) frequently state outdated API versions, deprecated frameworks, old pricing tiers, and former company leadership with high confidence.

**FreshGuard AI** is a Stale-Answer Detector & Live Fact Verification system that takes any LLM-generated response and evaluates whether its claims are still accurate and up to date:

1. **Claim Identification:** Breaks an LLM-generated response into individual verifiable statements.
2. **Smart Freshness Routing:** Distinguishes timeless foundational definitions (verified immediately with **0 unnecessary web searches**) from time-sensitive claims (versions, leadership, regulations, pricing, maintenance lifecycles).
3. **Live Web Verification (Tavily AI):** Queries live web sources via **Tavily Search API** to retrieve current evidence and reference URLs.
4. **Structured Reasoning (Bifrost AI Gateway):** Routes verification prompts through **Bifrost by Maxim AI** (`x-bf-provider: groq`, `x-bf-cache-control: semantic-cache`) with automatic model failover.
5. **Freshness Scoring (0–100):** Visualizes overall response health on an interactive **CIBIL-style Freshness Score Gauge** and classifies every statement as **Verified**, **Needs Review**, or **Stale / Outdated**.

---

## 🏗️ Mandatory Technology Stack

| Technology | Role in FreshGuard AI Architecture |
| :--- | :--- |
| **Tavily AI** | Performs real-time web searches and extracts authoritative snippets and comparison URLs for time-sensitive claims. |
| **Bifrost by Maxim AI** | Unified AI Gateway routing LLM verification calls with semantic caching (`x-bf-cache-control: semantic-cache`) and automatic model failover (`llama-3.3-70b-versatile` $\rightarrow$ `llama-3.1-8b-instant`). |
| **FastAPI (Python)** | Asynchronous backend serving the verification REST API (`/api/verify`). |
| **Tailwind CSS + SVG Gauge** | Clean two-page verification interface with a CIBIL-style semi-circular freshness score gauge and category filtering. |

---

## ⚙️ Quick Start (Run Locally)

### 1. Install Dependencies
```bash
pip install -r requirements.txt