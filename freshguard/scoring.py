"""Evidence-based freshness scoring.

Each claim gets an evidence-strength score (0-100) built from four parts:
  authority     0-30  tier of the cited source (primary / secondary)
  recency       0-25  age of the newest cited source (matters most for time-sensitive claims)
  corroboration 0-20  how many vetted sources agree with the verdict
  grounding     0-25  quote verified in the source + independent audit result
The freshness score then sits inside the band of the claim's verdict:
  Verified 75-100, Needs Review 50-74, Stale / Outdated 0-49
so the score and the label can never disagree. For stale claims, stronger
evidence of staleness gives a LOWER freshness score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

LABELS = {"VERIFIED": "Verified", "OUTDATED": "Stale / Outdated", "NEEDS_REVIEW": "Needs Review"}
BANDS = {"Verified": (75, 100), "Needs Review": (50, 74), "Stale / Outdated": (0, 49)}


def evidence_strength(
    verdict: str,
    time_sensitive: bool,
    cited: Optional[Dict[str, Any]],
    supporting: List[Dict[str, Any]],
    quote_ok: bool,
    audit_status: str,
) -> Dict[str, Any]:
    bd = {"authority": 0, "recency": 0, "corroboration": 0, "grounding": 0}
    if verdict in ("VERIFIED", "OUTDATED") and cited:
        bd["authority"] = {"primary": 30, "secondary": 20}.get(cited.get("authority_tier"), 5)
        ages = [s.get("days_old") for s in supporting if s.get("days_old") is not None]
        newest = min(ages) if ages else None
        if time_sensitive:
            if newest is None:
                bd["recency"] = 8
            elif newest <= 30:
                bd["recency"] = 25
            elif newest <= 90:
                bd["recency"] = 20
            elif newest <= 365:
                bd["recency"] = 12
            else:
                bd["recency"] = 4
        else:
            bd["recency"] = 20 if newest is None or newest <= 3 * 365 else 15
        n = len(supporting)
        bd["corroboration"] = 20 if n >= 3 else (15 if n == 2 else (10 if n == 1 else 0))
        bd["grounding"] = (10 if quote_ok else 0) + {"passed": 15, "partial": 6}.get(audit_status, 0)
    total = min(100, sum(bd.values()))
    return {"total": total, "breakdown": bd}


def freshness_score(label: str, strength: int) -> int:
    lo, hi = BANDS[label]
    span = hi - lo
    if label == "Stale / Outdated":
        return int(round(hi - span * strength / 100))
    return int(round(lo + span * strength / 100))


def aggregate(claims: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(claims)
    stale = sum(1 for c in claims if c["verdict"] == "Stale / Outdated")
    review = sum(1 for c in claims if c["verdict"] == "Needs Review")
    verified = sum(1 for c in claims if c["verdict"] == "Verified")
    if total == 0:
        return {"overall_verdict": "No Verifiable Claims", "overall_score": None, "risk_level": "UNKNOWN",
                "total_claims": 0, "verified_count": 0, "stale_count": 0, "needs_review_count": 0}
    if stale:
        label, risk = "Stale / Outdated", "HIGH"
    elif review:
        label, risk = "Needs Review", "MEDIUM"
    else:
        label, risk = "Verified", "LOW"
    mean = sum(c["freshness_score"] for c in claims) / total
    lo, hi = BANDS[label]
    score = int(round(min(hi, max(lo, mean))))
    return {"overall_verdict": label, "overall_score": score, "risk_level": risk, "total_claims": total,
            "verified_count": verified, "stale_count": stale, "needs_review_count": review}
