"""Nexus learning — adjusts lead scores from logged call outcomes.

Stats-based learning is free and always used once enough calls are logged.
Optional OpenAI pass: at most ONE gpt-4o-mini call per cooldown window per
generate batch (never per lead).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import tracking
from paths import LEARN_CACHE_FILE

MIN_CALLS_STAT = 10
MIN_CALLS_OPENAI = 25
OPENAI_COOLDOWN_SEC = 4 * 3600
MAX_OPENAI_LEADS = 12
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _score_bucket(score: int) -> str:
    if score >= 90:
        return "90+"
    if score >= 75:
        return "75-89"
    return "60-74"


def _openai_enabled() -> bool:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return False
    flag = os.getenv("ATLAS_LEARN_OPENAI", os.getenv("NEXUS_LEARN_OPENAI", "1")).strip().lower()
    return flag in ("1", "true", "yes")


def _cache_read() -> dict:
    if not LEARN_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(LEARN_CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _cache_write(data: dict) -> None:
    try:
        LEARN_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def learning_signals() -> dict:
    """Build conversion patterns from the call database (no API cost)."""
    rows = tracking.all_calls_raw()
    total = len(rows)
    if total < MIN_CALLS_STAT:
        return {"ready": False, "total_calls": total}

    by_city: dict[str, dict] = {}
    by_site: dict[str, dict] = {
        "dead": {"calls": 0, "interested": 0, "clients": 0},
        "none": {"calls": 0, "interested": 0, "clients": 0},
    }
    by_bucket: dict[str, dict] = {}

    interested = 0
    for row in rows:
        city = (row.get("city") or "Unknown").strip().lower()
        if city not in by_city:
            by_city[city] = {"calls": 0, "interested": 0, "clients": 0}
        by_city[city]["calls"] += 1
        if row.get("outcome") in tracking.INTEREST_OUTCOMES:
            by_city[city]["interested"] += 1
            interested += 1
        if row.get("outcome") == "client":
            by_city[city]["clients"] += 1

        status = row.get("site_status") or ""
        if status in by_site:
            by_site[status]["calls"] += 1
            if row.get("outcome") in tracking.INTEREST_OUTCOMES:
                by_site[status]["interested"] += 1
            if row.get("outcome") == "client":
                by_site[status]["clients"] += 1

        score = row.get("score")
        if score is not None:
            bucket = _score_bucket(int(score))
            if bucket not in by_bucket:
                by_bucket[bucket] = {"calls": 0, "interested": 0}
            by_bucket[bucket]["calls"] += 1
            if row.get("outcome") in tracking.INTEREST_OUTCOMES:
                by_bucket[bucket]["interested"] += 1

    dead = by_site["dead"]
    none = by_site["none"]
    dead_ir = dead["interested"] / dead["calls"] if dead["calls"] else 0
    none_ir = none["interested"] / none["calls"] if none["calls"] else 0

    return {
        "ready": True,
        "total_calls": total,
        "avg_interest_rate": interested / total if total else 0,
        "dead_interest_rate": dead_ir,
        "no_interest_rate": none_ir,
        "dead_beats_none": dead_ir > none_ir + 0.05,
        "none_beats_dead": none_ir > dead_ir + 0.05,
        "by_city": by_city,
        "by_site": by_site,
        "by_bucket": by_bucket,
    }


def _stat_adjustment(lead: dict, signals: dict) -> tuple[int, str]:
    delta = 0
    notes: list[str] = []

    city = tracking.city_from_address(lead.get("address", "")).strip().lower()
    cs = signals["by_city"].get(city)
    if cs and cs["calls"] >= 3:
        rate = cs["interested"] / cs["calls"]
        if rate >= 0.35:
            delta += 8
            notes.append(f"{city.title()} converts well")
        elif rate >= 0.2 and rate > signals["avg_interest_rate"]:
            delta += 4
        elif rate == 0 and cs["calls"] >= 5:
            delta -= 6
            notes.append(f"{city.title()} low response")

    status = lead.get("site_status")
    if status == "dead" and signals.get("dead_beats_none"):
        delta += 5
        notes.append("dead sites trending")
    elif status == "none" and signals.get("none_beats_dead"):
        delta += 5
        notes.append("no-site leads trending")

    bucket = _score_bucket(int(lead.get("score") or 0))
    bs = signals["by_bucket"].get(bucket, {})
    if bs.get("calls", 0) >= 5:
        rate = bs["interested"] / bs["calls"]
        if rate >= 0.3:
            delta += 4
        elif rate == 0:
            delta -= 4

    delta = max(-12, min(12, delta))
    return delta, " · ".join(notes)


def _openai_batch_tweak(leads: list[dict], signals: dict) -> str:
    """One API call to nudge scores for the current batch. Returns status note."""
    if not _openai_enabled() or signals["total_calls"] < MIN_CALLS_OPENAI:
        return ""

    cache = _cache_read()
    last = float(cache.get("last_openai_at") or 0)
    if time.time() - last < OPENAI_COOLDOWN_SEC:
        return "AI learning on cooldown (saves API usage)"

    try:
        import requests
    except ImportError:
        return ""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    top = sorted(leads, key=lambda x: -int(x.get("score") or 0))[:MAX_OPENAI_LEADS]
    payload = {
        "patterns": {
            "total_calls": signals["total_calls"],
            "dead_interest_pct": round(signals["dead_interest_rate"] * 100, 1),
            "no_interest_pct": round(signals["no_interest_rate"] * 100, 1),
            "top_cities": sorted(
                [
                    {"city": c, "rate": round(d["interested"] / d["calls"] * 100, 1)}
                    for c, d in signals["by_city"].items()
                    if d["calls"] >= 3
                ],
                key=lambda x: x["rate"],
                reverse=True,
            )[:5],
        },
        "leads": [
            {
                "phone": lead.get("phone"),
                "score": lead.get("score"),
                "site_status": lead.get("site_status"),
                "city": tracking.city_from_address(lead.get("address", "")),
                "reviews": lead.get("reviews"),
            }
            for lead in top
        ],
    }
    system = (
        "You help rank HVAC sales leads. Given call-history patterns and a batch "
        "of new leads, return JSON: {\"adjustments\": [{\"phone\": \"...\", "
        "\"delta\": <-12 to 12>, \"reason\": \"short\"}]}. Only include leads "
        "that deserve a meaningful nudge. Max 5 entries."
    )
    try:
        resp = requests.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 350,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
            timeout=45,
        )
        if not resp.ok:
            return ""
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        by_phone = {lead.get("phone"): lead for lead in leads}
        applied = 0
        for item in data.get("adjustments") or []:
            phone = item.get("phone")
            lead = by_phone.get(phone)
            if not lead:
                continue
            delta = max(-12, min(12, int(item.get("delta", 0))))
            if not delta:
                continue
            base = int(lead.get("score") or 0)
            lead["score"] = max(0, min(100, base + delta))
            lead["learn_delta"] = lead.get("learn_delta", 0) + delta
            reason = str(item.get("reason", "")).strip()
            if reason:
                lead["reason"] = f"{lead.get('reason', '')} · AI: {reason}".strip(" ·")
            applied += 1
        _cache_write({"last_openai_at": time.time(), "applied": applied})
        return f"AI refined {applied} lead(s)" if applied else ""
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return ""


def apply_learning(leads: list[dict]) -> str:
    """Apply learning to a scored batch. Re-sorts by score. Returns status note."""
    if not leads:
        return ""

    signals = learning_signals()
    if not signals.get("ready"):
        return f"Learning starts after {MIN_CALLS_STAT} logged calls"

    adjusted = 0
    for lead in leads:
        delta, note = _stat_adjustment(lead, signals)
        if delta:
            base = int(lead.get("score") or 0)
            lead["score"] = max(0, min(100, base + delta))
            lead["learn_delta"] = delta
            if note:
                lead["reason"] = f"{lead.get('reason', '')} · Learned: {note}".strip(" ·")
            adjusted += 1

    ai_note = _openai_batch_tweak(leads, signals)
    leads.sort(key=lambda x: -int(x.get("score") or 0))

    parts = [f"Learned from {signals['total_calls']} calls"]
    if adjusted:
        parts.append(f"{adjusted} stat tweak(s)")
    if ai_note:
        parts.append(ai_note)
    return " · ".join(parts)


def learning_status() -> dict:
    """Summary for owner dashboard."""
    signals = learning_signals()
    cache = _cache_read()
    last_ai = float(cache.get("last_openai_at") or 0)
    ai_cooldown = max(0, int(OPENAI_COOLDOWN_SEC - (time.time() - last_ai)))
    return {
        "total_calls": signals.get("total_calls", 0),
        "active": bool(signals.get("ready")),
        "min_calls": MIN_CALLS_STAT,
        "openai_enabled": _openai_enabled(),
        "openai_min_calls": MIN_CALLS_OPENAI,
        "openai_cooldown_sec": ai_cooldown,
    }
