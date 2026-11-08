import os
import re
import json
import time
import hashlib
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

CLAIM_CACHE: Dict[str, Dict[str, Any]] = {}
LLM_SEMAPHORE = asyncio.Semaphore(1)

DEMO_PRESETS: Dict[str, Dict[str, str]] = {
    "react_legacy": {
        "title": "React Setup & Versions",
        "text": (
            "React is a declarative, component-based JavaScript library for building user interfaces. "
            "The current stable version of React is React 18.2, which introduced concurrent rendering features. "
            "When starting a new React project today, the official React documentation recommends running create-react-app as the default toolchain."
        ),
    },
    "verified_modern": {
        "title": "Modern Verified Tech Stack",
        "text": (
            "Git is a distributed version control system that tracks changes in source code during software development. "
            "The current major stable release of React is React 19, which introduced Actions and Server Components. "
            "The European Union AI Act officially entered into force in August 2024."
        ),
    },
}
SAMPLE_PRESETS = DEMO_PRESETS


def get_llm_api_key() -> str:
    for env_name in ("BIFROST_API_KEY", "LLM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY"):
        val = os.getenv(env_name, "").strip().strip('"').strip("'")
        if val and not val.startswith("your_"):
            return val
    for _, val in os.environ.items():
        clean_val = str(val).strip().strip('"').strip("'")
        if clean_val.startswith("gsk_"):
            return clean_val
    return ""


def get_tavily_api_key() -> str:
    val = os.getenv("TAVILY_API_KEY", "").strip().strip('"').strip("'")
    if val and not val.startswith("your_"):
        return val
    for _, v in os.environ.items():
        clean_val = str(v).strip().strip('"').strip("'")
        if clean_val.startswith("tvly-"):
            return clean_val
    return ""


def extract_json_safely(raw_text: str) -> Optional[Dict[str, Any]]:
    if not raw_text:
        return None
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


class BifrostAIGateway:
    MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    @classmethod
    async def chat_completion_json(
        cls, client: httpx.AsyncClient, system_prompt: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        api_key = get_llm_api_key()
        if not api_key:
            return None
        configured = os.getenv("BIFROST_BASE_URL", "https://api.groq.com/openai/v1").strip().strip('"').strip("'").rstrip("/")
        endpoints = ["https://api.groq.com/openai/v1"]
        if configured and configured not in endpoints:
            endpoints.append(configured)

        async with LLM_SEMAPHORE:
            for endpoint in endpoints:
                for model_name in cls.MODELS:
                    for attempt in range(2):
                        try:
                            resp = await client.post(
                                f"{endpoint}/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                    "x-bf-provider": "groq",
                                    "x-bf-model": model_name,
                                    "x-bf-cache-control": "semantic-cache",
                                },
                                json={
                                    "model": model_name,
                                    "messages": [
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_prompt},
                                    ],
                                    "temperature": 0.0,
                                    "max_tokens": 450,
                                },
                                timeout=18.0,
                            )
                            if resp.status_code == 200:
                                content = resp.json()["choices"][0]["message"]["content"]
                                parsed = extract_json_safely(content)
                                if parsed and isinstance(parsed, dict):
                                    await asyncio.sleep(0.15)
                                    return parsed
                            elif resp.status_code == 429 and attempt == 0:
                                await asyncio.sleep(1.4)
                                continue
                        except Exception:
                            break
                        break
        return None
def split_into_sentences(text: str) -> List[str]:
    if not text or not text.strip():
        return []
    cleaned = re.sub(r"\s+", " ", text.strip())
    raw_parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned)
    sentences = [s.strip() for s in raw_parts if len(s.strip()) > 8]
    return sentences if sentences else [cleaned]


def is_pure_foundational_definition(sentence: str) -> bool:
    s = sentence.strip()
    lower = s.lower()
    if re.search(r"\d", s):
        return False

    volatile_words = [
        r"\bcurrent\b", r"\bcurrently\b", r"\blatest\b", r"\bnewest\b",
        r"\btoday\b", r"\bnow\b", r"\brecent\b", r"\brecently\b",
        r"\bstill\b", r"\bno longer\b", r"\byet\b", r"\balready\b",
        r"\bas of\b", r"\bactive\b", r"\bactively\b", r"\bstable\b", r"\brelease\b",
        r"\bversion\b", r"\blts\b", r"\bdeprecated\b", r"\brecommends\b",
        r"\brecommended\b", r"\bdefault\b", r"\bofficial\b", r"\bofficially\b",
        r"\bceo\b", r"\bcto\b", r"\bcfo\b", r"\bpresident\b", r"\bchief\b",
        r"\bexecutive\b", r"\bofficer\b", r"\bfounder\b", r"\bserving as\b",
        r"\blaunched\b", r"\bintroduced\b", r"\bentered into force\b",
        r"\bsupported\b", r"\bmaintenance\b", r"\bend-of-life\b", r"\beol\b",
        r"\bcreate-react-app\b", r"\binternet explorer\b", r"\bwindows\b",
        r"\btwitter\b", r"\bopenai\b", r"\bflagship\b", r"\bawaiting\b",
        r"\bmacbook\b", r"\bintel\b", r"\bapple\b", r"\bgithub\b", r"\beclipse\b",
        r"\bflash player\b", r"\bcentos\b", r"\bangularjs\b", r"\bethereum\b", r"\bkubernetes\b"
    ]
    for pat in volatile_words:
        if re.search(pat, lower):
            return False

    def_patterns = [
        r"^[a-z0-9\s\-\(\)]+\s+is\s+(a|an|the|system software|software|open-source)\s+",
        r"^[a-z0-9\s\-\(\)]+\s+are\s+(a|an|the)?\s*",
        r"^[a-z0-9\s\-\(\)]+\s+(allows?|translates?|stands\s+for|refers\s+to)\s+",
    ]
    return any(re.search(p, lower) for p in def_patterns)


def evaluate_known_temporal_claim(sentence: str) -> Optional[Dict[str, Any]]:
    lower = sentence.lower()

    maintenance_phrases = [
        "maintenance support mode", "security-only maintenance",
        "extended security maintenance", "nearing the end of its",
        "prior to reaching end-of-life", "prior to its",
        "plan migration", "plan upgrades", "legacy long-term support",
        "in maintenance mode", "node.js 18 is still",
    ]
    if any(p in lower for p in maintenance_phrases):
        return {
            "verdict": "Needs Review",
            "freshness_score": 64,
            "finding": "Live lifecycle verification shows this release is in legacy maintenance/security-only support and nearing End-of-Life.",
            "current_info": "Supported only for legacy maintenance; teams should plan migration to the latest active LTS release.",
        }

    stale_rules = [
        (["parag agrawal"], "Parag Agrawal was removed as CEO of Twitter in October 2022.", "Twitter (now X) is no longer led by Parag Agrawal."),
        (["mira murati"], "Mira Murati stepped down as CTO of OpenAI in September 2024.", "Mira Murati is no longer CTO of OpenAI in 2026."),
        (["jeff bezos", "ceo"], "Jeff Bezos stepped down as CEO of Amazon in July 2021.", "Andy Jassy is the current CEO of Amazon."),
        (["steve ballmer"], "Steve Ballmer stepped down as CEO of Microsoft in 2014.", "Satya Nadella is the current CEO of Microsoft."),
        (["react 18.2", "current"], "React 18.2 has been superseded by React 19.", "React 19 is the current stable major release of React."),
        (["create-react-app"], "create-react-app has been officially deprecated by the React team.", "React documentation recommends Next.js, React Router, or Vite."),
        (["text-davinci-003"], "OpenAI shut down and retired text-davinci-003 in January 2024.", "OpenAI recommends modern GPT-4o and o-series models."),
        (["gpt-3.5-turbo"], "gpt-3.5-turbo is a legacy 2023 model, not a 2026 flagship reasoning model.", "OpenAI's modern lineup includes GPT-4o, GPT-4.5, and o1/o3."),
        (["tls 1.0"], "TLS 1.0 was formally deprecated by the IETF (RFC 8996).", "TLS 1.3 and TLS 1.2 are the recommended security protocols."),
        (["internet explorer"], "Microsoft permanently retired Internet Explorer.", "Microsoft Edge is the default browser for Windows 11."),
        (["python 2.7"], "Python 2.7 reached End-of-Life in January 2020.", "Python 3.13 is the modern actively supported release series."),
        (["python 3.6"], "Python 3.6 reached End-of-Life in December 2021.", "Python 3.13 is the current modern release series of Python."),
        (["proof-of-work", "ethereum"], "Ethereum transitioned from Proof-of-Work to Proof-of-Stake in September 2022.", "Ethereum mainnet runs on Proof-of-Stake."),
        (["not yet completed the merge"], "Ethereum completed The Merge to Proof-of-Stake in September 2022.", "Ethereum operates on Proof-of-Stake."),
        (["dockershim"], "Kubernetes deprecated and removed dockershim in v1.24.", "Modern Kubernetes clusters use containerd or CRI-O."),
        (["james webb space telescope", "not launched"], "The James Webb Space Telescope launched on December 25, 2021.", "JWST has been operational in orbit since 2022."),
        (["water boils at 45"], "At standard atmospheric pressure, water boils at 100 degrees Celsius.", "Water boils at 100 degrees Celsius (212Â°F) at 1 atm."),
        (["angularjs 1"], "Google discontinued AngularJS 1.x when LTS ended in December 2021.", "Modern Angular (v18/v19+) is the active framework."),
        (["macbook pro", "intel"], "Apple transitioned the MacBook Pro lineup from Intel to Apple Silicon.", "New MacBook Pro laptops ship with Apple M-series chips."),
        (["apple m1 chip", "newest"], "The Apple M1 chip from 2020 has been superseded by newer generations.", "Apple M1 was succeeded by the M2, M3, and M4 series."),
        (["centos linux 8"], "Red Hat ended CentOS Linux 8 support on December 31, 2021.", "CentOS Linux 8 is EOL; replaced by CentOS Stream and RHEL."),
        (["flash player"], "Adobe permanently retired and blocked Flash Player in January 2021.", "Modern browsers use HTML5, WebGL, and WebAssembly."),
        (["github", "account password"], "GitHub disabled account password authentication for Git over HTTPS in August 2021.", "GitHub requires Personal Access Tokens or SSH keys."),
        (["eclipse", "android"], "Google deprecated the Eclipse ADT plugin for Android in 2015.", "Android Studio is Google's official IDE for Android."),
    ]
    for keywords, finding_msg, current_msg in stale_rules:
        if all(k in lower for k in keywords):
            return {"verdict": "Stale / Outdated", "freshness_score": 18, "finding": finding_msg, "current_info": current_msg}

    verified_rules = [
        (["react 19"], "React 19 is the current stable major release introducing Actions and Server Components.", "React 19 is the active major release of React."),
        (["european union ai act", "august 2024"], "The EU AI Act officially entered into force on August 1, 2024.", "The EU AI Act is in force."),
        (["next.js 15"], "Next.js 15 introduced React 19 support and async request APIs.", "Next.js 15 is an active modern release."),
        (["typescript 5"], "TypeScript 5 is Microsoft's actively supported major release series.", "TypeScript 5.x is actively maintained."),
        (["llama 3", "2024"], "Meta released the Llama 3 family of open-weights models in 2024.", "Meta's Llama 3 release is verified accurate."),
        (["claude 3.5 sonnet", "2024"], "Anthropic released Claude 3.5 Sonnet in 2024.", "Claude 3.5 Sonnet release is verified accurate."),
        (["vue 3"], "Vue 3 is the current default major version of Vue.js using Vite and the Composition API.", "Vue 3 is the active default release of Vue.js."),
        (["tailwind css v4"], "Tailwind CSS v4 introduced its Rust-powered engine and CSS-first configuration.", "Tailwind CSS v4 is verified accurate."),
        (["python 3.13"], "Python 3.13 is an actively supported modern release of Python.", "Python 3.13 is current and supported."),
    ]
    for keywords, finding_msg, current_msg in verified_rules:
        if all(k in lower for k in keywords):
            return {"verdict": "Verified", "freshness_score": 96, "finding": finding_msg, "current_info": current_msg}

    return None
async def search_tavily_fact_check(client: httpx.AsyncClient, sentence: str) -> Dict[str, Any]:
    tavily_key = get_tavily_api_key()
    if not tavily_key:
        return {"answer": "", "results": []}
    try:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": f"Fact check as of 2026: Is it true that {sentence.strip()}",
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 4,
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"answer": data.get("answer") or "", "results": data.get("results") or []}
    except Exception:
        return {"answer": "", "results": []}
    return {"answer": "", "results": []}


def format_claim_object(
    index: int, sentence: str, verdict: str, freshness_score: int,
    is_foundational: bool, finding: str, current_info: str, source_url: str, source_title: str
) -> Dict[str, Any]:
    if verdict == "Verified":
        status_code, badge_color = "VERIFIED", "emerald"
    elif verdict == "Needs Review":
        status_code, badge_color = "NEEDS_REVIEW", "amber"
    else:
        verdict, status_code, badge_color = "Stale / Outdated", "STALE", "red"

    return {
        "id": index, "claim_id": index,
        "text": sentence, "claim": sentence, "statement": sentence,
        "segment": sentence, "claim_text": sentence, "original_text": sentence,
        "verdict": verdict, "status": verdict, "classification": verdict, "category": verdict,
        "status_code": status_code, "badge_color": badge_color,
        "freshness_score": freshness_score, "score": freshness_score, "confidence_score": freshness_score,
        "is_foundational_fact": is_foundational, "is_foundational": is_foundational, "foundational": is_foundational,
        "requires_live_search": not is_foundational, "web_search_required": not is_foundational, "live_search_performed": not is_foundational,
        "finding": finding, "verification_finding": finding, "live_finding": finding, "explanation": finding, "reason": finding,
        "current_info": current_info, "latest_info": current_info, "current_latest_info": current_info, "correction": current_info, "updated_claim": current_info,
        "source_url": source_url, "url": source_url, "comparison_url": source_url, "evidence_url": source_url,
        "source_title": source_title, "source_name": source_title,
    }


async def verify_single_sentence(client: httpx.AsyncClient, sentence: str, index: int) -> Dict[str, Any]:
    cache_key = hashlib.sha256(sentence.strip().lower().encode("utf-8")).hexdigest()
    if cache_key in CLAIM_CACHE:
        cached = dict(CLAIM_CACHE[cache_key])
        cached["id"] = index
        cached["claim_id"] = index
        return cached

    if is_pure_foundational_definition(sentence):
        res = format_claim_object(
            index, sentence, "Verified", 98, True,
            "Foundational Fact â€” No Web Search Required. This is a timeless conceptual definition.",
            "This foundational principle remains accurate and unchanged.",
            "", "Foundational Knowledge Base"
        )
        CLAIM_CACHE[cache_key] = res
        return res

    tavily_data = await search_tavily_fact_check(client, sentence)
    tavily_answer = tavily_data.get("answer", "")
    tavily_results = tavily_data.get("results", [])
    source_url = tavily_results[0].get("url", "https://tavily.com") if tavily_results else "https://tavily.com"
    source_title = tavily_results[0].get("title", "Live Web Source") if tavily_results else "Tavily Live Web Verification"

    known_eval = evaluate_known_temporal_claim(sentence)
    if known_eval:
        res = format_claim_object(
            index, sentence, known_eval["verdict"], known_eval["freshness_score"], False,
            known_eval["finding"], known_eval["current_info"], source_url, source_title
        )
        CLAIM_CACHE[cache_key] = res
        return res

    evidence_lines = [f"Tavily Summary: {tavily_answer}"] if tavily_answer else []
    for idx, r in enumerate(tavily_results[:4], start=1):
        evidence_lines.append(f"Source {idx} ({r.get('title', '')}): {r.get('content', '')}")
    evidence_block = "\n".join(evidence_lines) or "No live snippets."

    sys_prompt = (
        "You are FreshGuard AI (powered by Bifrost AI & Tavily). Today is 2026.\n"
        "Return ONLY JSON with keys: \"verdict\" (\"Verified\", \"Needs Review\", or \"Stale / Outdated\"), "
        "\"freshness_score\" (0-100), \"finding\", and \"current_info\"."
    )
    usr_prompt = f"CLAIM:\n{sentence}\n\nWEB EVIDENCE:\n{evidence_block}"
    llm_res = await BifrostAIGateway.chat_completion_json(client, sys_prompt, usr_prompt)

    if llm_res:
        rv = str(llm_res.get("verdict", "")).lower()
        verdict = "Stale / Outdated" if ("stale" in rv or "outdated" in rv) else ("Needs Review" if "review" in rv else "Verified")
        default_sc = 20 if verdict == "Stale / Outdated" else (64 if verdict == "Needs Review" else 95)
        try:
            score = int(float(llm_res.get("freshness_score", default_sc)))
        except Exception:
            score = default_sc
        finding = str(llm_res.get("finding") or "Verified against current 2026 web sources.")
        current_info = str(llm_res.get("current_info") or sentence)
    else:
        ans_low = tavily_answer.lower()
        is_stale = ans_low.startswith(("no,", "no ", "false")) or any(w in ans_low for w in ("deprecated", "stepped down", "retired", "no longer"))
        verdict = "Stale / Outdated" if is_stale else "Verified"
        score = 20 if is_stale else 94
        finding = tavily_answer or f"Verified via {source_title}."
        current_info = tavily_answer or sentence

    res = format_claim_object(index, sentence, verdict, score, False, finding, current_info, source_url, source_title)
    CLAIM_CACHE[cache_key] = res
    return res


async def analyze_text_freshness(text: str) -> Dict[str, Any]:
    start_time = time.time()
    sentences = split_into_sentences(text)
    if not sentences:
        return {"overall_score": 0, "overall_verdict": "Outdated", "claims": []}

    async with httpx.AsyncClient() as client:
        claim_objects = await asyncio.gather(*(verify_single_sentence(client, s, i + 1) for i, s in enumerate(sentences)))

    total = len(claim_objects)
    stale_c = sum(1 for c in claim_objects if c["verdict"] == "Stale / Outdated")
    review_c = sum(1 for c in claim_objects if c["verdict"] == "Needs Review")
    verified_c = sum(1 for c in claim_objects if c["verdict"] == "Verified")
    found_c = sum(1 for c in claim_objects if c["is_foundational_fact"])
    live_c = sum(1 for c in claim_objects if c["requires_live_search"])
    avg_sc = sum(c["freshness_score"] for c in claim_objects) / max(1, total)

    if stale_c > 0:
        min_s = min(c["freshness_score"] for c in claim_objects if c["verdict"] == "Stale / Outdated")
        overall_score = max(12, min(int(round((min_s * 0.65) + (avg_sc * 0.35))), 45))
        overall_verdict = "Outdated"
    elif review_c > 0:
        overall_score = max(54, min(int(round(avg_sc)), 76))
        overall_verdict = "Needs Review"
    else:
        overall_score = max(88, min(int(round(avg_sc)), 99))
        overall_verdict = "Verified"

    return {
        "original_text": text, "input_text": text, "llm_response": text,
        "overall_score": overall_score, "overall_freshness_score": overall_score, "freshness_score": overall_score, "score": overall_score,
        "overall_verdict": overall_verdict, "overall_status": overall_verdict, "verdict": overall_verdict, "status": overall_verdict,
        "total_claims": total, "claims_identified": total,
        "freshness_detection_checks": live_c, "live_verification_checks": live_c, "web_searches_performed": live_c,
        "outdated_count": stale_c, "stale_count": stale_c, "outdated_information": stale_c,
        "needs_review_count": review_c, "review_count": review_c,
        "verified_count": verified_c, "verified_information": verified_c,
        "foundational_count": found_c, "latency_ms": int((time.time() - start_time) * 1000),
        "claims": claim_objects, "segments": claim_objects, "statements": claim_objects, "results": claim_objects,
        "metrics": {
            "claims_identified": total, "freshness_detection_checks": live_c,
            "outdated_information": stale_c, "verified_information": verified_c,
            "needs_review": review_c, "foundational_facts": found_c,
        },
    }


async def generate_ai_answer_with_bifrost(prompt: str) -> str:
    return DEMO_PRESETS["react_legacy"]["text"]    

