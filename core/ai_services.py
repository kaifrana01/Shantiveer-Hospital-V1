from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AIExplanation:
    score: float
    reasons: Tuple[str, ...]
    confidence: float

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "reasons": list(self.reasons),
            "confidence": self.confidence,
        }


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def triage_score(
    *,
    category: str = "",
    status: str = "",
    diagnosis_text: str = "",
    waiting_minutes: int = 0,
    is_icu: bool = False,
) -> AIExplanation:
    """Compute an urgency score + reasons.

    Inputs are optional because current DB may not contain rich vitals.
    """

    cat = _normalize(category)
    st = _normalize(status)
    dx = _normalize(diagnosis_text)

    score = 0.0
    reasons: List[str] = []

    # Category / ICU
    if "icu" in cat or is_icu:
        score += 40
        reasons.append("ICU category / ICU flag")
    if "emerg" in cat or "emergency" in cat:
        score += 25
        reasons.append("Emergency category")

    # Status
    if st in {"admitted", "open", "active"}:
        score += 10
        reasons.append("Currently admitted/active")
    if "pending" in st:
        score += 8
        reasons.append("Pending action")

    # Diagnosis keywords (very lightweight)
    keyword_map = [
        (r"chest\s*pain|mi|heart\s*attack|angina|cad", 18, "Cardiac symptom keywords"),
        (r"stroke|tia|hemiparesis|slurred\s*speech", 20, "Neurological red-flag keywords"),
        (r"sepsis|septic", 25, "Sepsis keywords"),
        (r"breath|dyspnea|shortness\s*of\s*breath|copd|asthma", 16, "Respiratory distress keywords"),
        (r"unconscious|coma|unresponsive", 28, "Altered consciousness keywords"),
        (r"uncontrolled\s*bleeding|bleed", 22, "Bleeding keywords"),
        (r"fracture|trauma|fall", 10, "Trauma keywords"),
    ]

    for pattern, add, reason in keyword_map:
        if re.search(pattern, dx):
            score += add
            reasons.append(reason)

    # Waiting time
    if waiting_minutes >= 120:
        score += 20
        reasons.append("Waiting > 2 hours")
    elif waiting_minutes >= 60:
        score += 12
        reasons.append("Waiting > 1 hour")
    elif waiting_minutes >= 30:
        score += 6
        reasons.append("Waiting > 30 minutes")

    # Clamp
    score = max(0.0, min(100.0, score))

    # Confidence: higher when more signals exist
    signal_count = 0
    if cat:
        signal_count += 1
    if st:
        signal_count += 1
    if dx:
        signal_count += 1
    if waiting_minutes > 0:
        signal_count += 1

    confidence = 0.55 if signal_count <= 1 else 0.7 if signal_count == 2 else 0.82

    if not reasons:
        reasons = ["No strong triage signals found; defaulting to baseline urgency"]

    return AIExplanation(score=score, reasons=tuple(reasons), confidence=confidence)


def summarize_prescription(text: str, *, max_chars: int = 220) -> str:
    """Generate a short summary of prescription text.

    This is an extractive/heuristic summarizer: chooses key sentences and
    formats a concise output.
    """

    raw = text or ""
    t = " ".join(raw.split())
    if not t:
        return "No prescription text available for AI summary."

    # Try to pick sentences that look like diagnosis/advice/medicine.
    parts = re.split(r"(?<=[.!?])\s+", t)
    keywords = ["diagnos", "advice", "take", "tablet", "tab", "syrup", "caps", "inj", "dose", "mg", "x ", "daily"]

    scored: List[Tuple[int, str]] = []
    for p in parts:
        pl = p.lower()
        score = sum(1 for k in keywords if k in pl)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = [p for s, p in scored if s > 0][:3]

    if not chosen:
        chosen = parts[:2]

    summary = " | ".join(chosen)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1].rstrip() + "…"

    return summary


def recommend_inventory_reorder(
    *,
    stock: int = 0,
    buffer: int = 0,
    unit: str = "",
    recent_consumption_per_day: Optional[float] = None,
    lead_time_days: int = 7,
) -> Dict:
    """Suggest reorder quantity using heuristic policy.

    If recent consumption is unknown, use buffer policy.
    """

    stock = int(stock or 0)
    buffer = int(buffer or 0)

    reasons: List[str] = []

    # Baseline logic
    if stock <= 0:
        urgency = "critical"
        reasons.append("Stock is zero")
    elif stock < buffer:
        urgency = "low"
        reasons.append("Stock is below buffer")
    else:
        urgency = "ok"
        reasons.append("Stock is above buffer")

    recommended_qty = 0

    if recent_consumption_per_day is not None and recent_consumption_per_day > 0:
        # Order enough to cover lead time + buffer
        horizon = lead_time_days + max(buffer, 0) / max(1.0, recent_consumption_per_day)
        recommended_qty = int(round(recent_consumption_per_day * horizon - stock))
        reasons.append("Using estimated consumption + lead time")
    else:
        # Simple buffer refill
        if urgency == "critical":
            recommended_qty = max(buffer, 1)
            reasons.append("Refill policy based on buffer")
        elif urgency == "low":
            recommended_qty = max(buffer - stock, 1)
            reasons.append("Top-up to buffer level")
        else:
            recommended_qty = 0

    recommended_qty = max(0, recommended_qty)

    confidence = 0.75 if recent_consumption_per_day is not None else 0.6

    return {
        "urgency": urgency,
        "recommended_qty": recommended_qty,
        "unit": unit,
        "confidence": confidence,
        "reasons": reasons,
    }


def recommend_lab_tests(diagnosis_text: str, *, top_k: int = 5) -> List[Dict]:
    """Suggest lab tests using diagnosis keyword mapping.

    Returns list of {test_keyword, reason, weight}.
    """

    dx = _normalize(diagnosis_text)

    # Keyword -> recommended tests mapping
    mapping = [
        (r"fever|chills|infection|sepsis", "CBC (Complete Blood Count)", 0.9, "Infection/fever symptoms"),
        (r"cough|sputum|pneumonia|tb", "Chest X-Ray / Relevant Respiratory Panel", 0.75, "Respiratory symptom keywords"),
        (r"diarrhea|vomiting|gastro|dehydration", "Serum Electrolytes + RFT", 0.8, "GI illness / dehydration"),
        (r"uti|burning urine|dysuria", "Urine Routine (R/M/E) + Culture", 0.85, "UTI related keywords"),
        (r"diabetes|hba1c|high sugar", "Fasting/PP Glucose + HbA1c", 0.9, "Diabetes keywords"),
        (r"kidney|creatinine|rft", "Renal Function Test (RFT)", 0.85, "Renal keywords"),
        (r"chest pain|cardiac|heart|angina|mi", "Troponin + ECG (if available)", 0.8, "Cardiac symptom keywords"),
        (r"anemia|hb|hemoglobin", "CBC + Iron Profile (if needed)", 0.75, "Anemia keywords"),
    ]

    hits: List[Tuple[float, str, float, str]] = []
    for pattern, test, weight, reason in mapping:
        if re.search(pattern, dx):
            hits.append((weight, test, weight, reason))

    if not hits:
        # Generic baseline suggestions
        return [
            {"test": "CBC", "reason": "General screening for inflammation/infection", "weight": 0.5},
            {"test": "RFT/Electrolytes", "reason": "Baseline renal/electrolyte check", "weight": 0.45},
        ][:top_k]

    # Sort by weight desc
    hits.sort(key=lambda x: x[0], reverse=True)

    results = []
    for _, test, weight, reason in hits[:top_k]:
        results.append({"test": test, "reason": reason, "weight": weight})

    return results

