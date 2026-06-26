"""Lead generation jobs — Nexus engine inside Atlas."""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import uuid

import simple_scraper as engine
from florida_cities import FLORIDA_CITIES
from paths import HISTORY_FILE, JOBS_DIR

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
RATE_LOCK = threading.Lock()
LAST_GENERATE: dict[str, float] = {}

MIN_REVIEWS = 3
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "600"))
CALLER_NAME = os.getenv("CALLER_NAME", "sebastien").strip()


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return {normalize_phone(p) for p in data.get("phone_keys", []) if normalize_phone(p)}
    except (json.JSONDecodeError, OSError):
        return set()


def save_history(keys: set[str]) -> None:
    HISTORY_FILE.write_text(
        json.dumps({"phone_keys": sorted(keys)}, indent=2), encoding="utf-8"
    )
    import storage

    storage.after_change("history")


def set_job(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {})
        JOBS[job_id].update(fields)
        try:
            (JOBS_DIR / f"{job_id}.json").write_text(
                json.dumps(JOBS[job_id]), encoding="utf-8"
            )
        except OSError:
            pass


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        if job_id in JOBS:
            return JOBS[job_id]
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        with JOBS_LOCK:
            JOBS[job_id] = data
        return data
    except (json.JSONDecodeError, OSError):
        return None


def check_rate_limit(key: str) -> tuple[bool, int]:
    now = time.time()
    with RATE_LOCK:
        last = LAST_GENERATE.get(key, 0)
        wait = int(RATE_LIMIT_SECONDS - (now - last))
        if wait > 0:
            return False, wait
        LAST_GENERATE[key] = now
        return True, 0


def run_pipeline(
    job_id: str,
    cities: list[str],
    top_n: int,
    extra_exclude: set[str],
    site_filter: str,
    industry: str = "hvac",
) -> None:
    del industry  # reserved for future niche expansion

    def progress(message: str) -> None:
        set_job(job_id, message=message)

    try:
        set_job(job_id, status="running", message="Finding businesses...")

        exclude = load_history() | extra_exclude
        rows = engine.collect_leads(
            cities,
            max_leads=top_n,
            pool_size=100,
            min_score=60,
            min_reviews=MIN_REVIEWS,
            use_openai=False,
            exclude_phones=exclude,
            progress=progress,
            opportunities_only=True,
            site_filter=site_filter,
        )

        if not rows:
            set_job(
                job_id,
                status="done",
                message="No high-scoring leads found. Try different cities.",
                leads=[],
            )
            return

        new_phones = {
            normalize_phone(r["phone"]) for r in rows if normalize_phone(r.get("phone", ""))
        }
        save_history(exclude | new_phones)

        from tracking import city_from_address

        payload = [
            {
                "name": r["name"],
                "phone": r["phone"],
                "rating": r["rating"],
                "reviews": r["reviews"],
                "website": r["website"] or "",
                "site_status": r["site_status"],
                "score": r["score"],
                "reason": r["reason"],
                "address": r["address"],
                "city": city_from_address(r.get("address", "")),
                "learn_delta": r.get("learn_delta"),
                "opener": engine.call_opener(r),
            }
            for r in rows
        ]

        set_job(
            job_id,
            status="done",
            message=f"Ready — {len(payload)} businesses to call.",
            leads=payload,
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        set_job(job_id, status="error", error=str(exc), message=str(exc))


def start_generation(
    *,
    mode: str,
    city: str,
    count: int,
    site_filter: str,
    industry: str,
    exclude_phones: list[str],
    rate_key: str,
) -> tuple[str | None, dict | None]:
    """Return (job_id, error_response_dict)."""
    if not os.getenv("GOOGLE_MAPS_API_KEY", "").strip():
        return None, {
            "error": "missing_api_key",
            "message": "Google Maps API key is not configured on the server.",
        }

    allowed, wait = check_rate_limit(rate_key)
    if not allowed:
        return None, {"error": "rate_limit", "retry_after": wait}

    count = max(3, min(int(count), 30))
    if site_filter not in ("all", "dead", "none"):
        site_filter = "all"

    extra_exclude = {normalize_phone(p) for p in exclude_phones if normalize_phone(p)}

    if mode == "city" and city:
        cities = [city]
    else:
        cities = random.sample(FLORIDA_CITIES, k=len(FLORIDA_CITIES))

    job_id = uuid.uuid4().hex
    set_job(job_id, status="queued", message="Queued...", leads=None, error=None)

    thread = threading.Thread(
        target=run_pipeline,
        args=(job_id, cities, count, extra_exclude, site_filter, industry),
        daemon=True,
    )
    thread.start()
    return job_id, None


def florida_cities_list() -> list[str]:
    return list(FLORIDA_CITIES)
