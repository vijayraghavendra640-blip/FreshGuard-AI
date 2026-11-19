"""Source helpers: credibility tiers, prompt-injection screening, sanitising,
publication-date parsing and quote grounding.

These were carried over from the original engine.py (where they were defined
but unused by the live pipeline) and are now wired into the pipeline.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional
from urllib.parse import urlparse

LOW_CREDIBILITY_DOMAINS = {
    "reddit.com", "quora.com", "medium.com", "blogspot.com",
    "wordpress.com", "tumblr.com", "x.com", "twitter.com",
    "facebook.com", "tiktok.com", "instagram.com", "pinterest.com",
    "linkedin.com", "youtube.com", "fandom.com", "urbandictionary.com",
}

PRIMARY_AUTHORITY_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
    "bloomberg.com", "ft.com", "wsj.com", "nytimes.com",
    "washingtonpost.com", "theguardian.com", "cnbc.com", "sec.gov",
    "nasa.gov", "who.int", "cdc.gov", "nih.gov",
    "europa.eu", "un.org", "worldbank.org", "imf.org",
    "nature.com", "science.org", "ieee.org", "acm.org",
    "python.org", "react.dev", "reactjs.org", "developer.mozilla.org",
    "docs.microsoft.com", "learn.microsoft.com", "cloud.google.com",
    "aws.amazon.com", "openai.com", "anthropic.com", "tavily.com",
    "github.com", "britannica.com", "wikipedia.org",
}

PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|lines|messages)\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"\bsystem\s+(?:override|prompt)\b",
    r"\bdeveloper\s+mode\b",
    r"\byou\s+are\s+now\s+an?\b",
    r"\breturn\s+verdict\s+verified\b",
    r"\bmark\s+(?:this|all|every)\s+(?:claim|claims|statement)s?\s+as\s+(?:verified|true)\b",
    r"<\s*/?\s*system\s*>",
    r"\[\s*system\s*\]",
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def detect_prompt_injection(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(re.search(pat, lowered) for pat in PROMPT_INJECTION_PATTERNS)


def sanitize_untrusted_text(text: str, max_len: int = 700) -> str:
    """Strip control chars, HTML tags, code fences and braces from web content."""
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", str(text))
    cleaned = re.sub(r"<[^>]{0,200}>", " ", cleaned)
    cleaned = re.sub(r"`{3,}", "'''", cleaned)
    cleaned = cleaned.replace("{", "(").replace("}", ")")
    return re.sub(r"\s+", " ", cleaned).strip()[:max_len]


def extract_domain(url: str) -> str:
    try:
        host = (urlparse((url or "").strip()).netloc or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_safe_http_url(url: str) -> bool:
    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def get_domain_authority_tier(url: str) -> str:
    domain = extract_domain(url)
    if not domain:
        return "none"
    if any(domain == d or domain.endswith("." + d) for d in LOW_CREDIBILITY_DOMAINS):
        return "low"
    if domain.endswith((".gov", ".edu", ".mil")) or ".gov." in domain:
        return "primary"
    if any(domain == d or domain.endswith("." + d) for d in PRIMARY_AUTHORITY_DOMAINS):
        return "primary"
    return "secondary"


def parse_publication_date(raw_date: Optional[str], snippet: str = "", url: str = "") -> Optional[datetime]:
    now = datetime.now(timezone.utc)
    if raw_date and str(raw_date).strip():
        s = str(raw_date).strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            if dt <= now:
                return dt
        except ValueError:
            pass
        try:  # RFC 2822 style, e.g. "Mon, 10 Nov 2025 14:00:00 GMT"
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(s)
            dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            if dt <= now:
                return dt
        except (TypeError, ValueError, IndexError):
            pass
    m_txt = re.search(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})\b",
        f"{raw_date or ''} {snippet[:250]}", re.IGNORECASE,
    )
    if m_txt:
        try:
            dt = datetime(int(m_txt.group(3)), MONTH_MAP[m_txt.group(1).lower()[:3]], int(m_txt.group(2)), tzinfo=timezone.utc)
            if dt <= now:
                return dt
        except ValueError:
            pass
    m_url = re.search(r"/(20\d{2})/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/", url or "")
    if m_url:
        try:
            dt = datetime(int(m_url.group(1)), int(m_url.group(2)), int(m_url.group(3)), tzinfo=timezone.utc)
            if dt <= now:
                return dt
        except ValueError:
            pass
    return None


def compute_days_old(dt: Optional[datetime]) -> Optional[int]:
    if not dt:
        return None
    return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))


def normalize_for_match(text: str) -> str:
    if not text:
        return ""
    s = re.sub(r"[‘’“”\"'`]", "", text.lower())
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[^a-z0-9\s\.\-%$]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str, min_tokens: int = 3, coverage: float = 0.9) -> bool:
    """True when `quote` appears in `text` verbatim (after normalisation), or when
    at least `coverage` of its tokens appear in order (tolerates ellipses/punctuation)."""
    nq, nt = normalize_for_match(quote), normalize_for_match(text)
    if not nq or not nt:
        return False
    q_tokens = [t.strip(".") for t in nq.split() if t.strip(".")]
    if len(q_tokens) < min_tokens:
        return False
    if nq in nt:
        return True
    t_tokens = [t.strip(".") for t in nt.split() if t.strip(".")]
    pos, hits = 0, 0
    for tok in q_tokens:
        for i in range(pos, len(t_tokens)):
            if t_tokens[i] == tok:
                hits += 1
                pos = i + 1
                break
    return hits / len(q_tokens) >= coverage


NUMBER_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")


def extract_numbers(text: str) -> List[str]:
    """Numbers normalised for comparison: '$1,200.00' -> '1200', '20%' -> '20'."""
    out: List[str] = []
    for raw in NUMBER_RE.findall(text or ""):
        n = raw.replace("$", "").replace(",", "").rstrip("%")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        if n:
            out.append(n)
    return out


def numbers_supported(text: str, evidence: Iterable[str]) -> List[str]:
    """Return numbers from `text` that do not occur in any evidence string."""
    ev_numbers = set()
    for e in evidence:
        ev_numbers.update(extract_numbers(e))
    return [n for n in dict.fromkeys(extract_numbers(text)) if n not in ev_numbers]
