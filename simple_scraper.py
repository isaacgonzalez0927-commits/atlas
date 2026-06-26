#!/usr/bin/env python3
"""
Simple HVAC lead scraper — Google Places + rubric scoring.

What it does, in plain steps:
  1. Searches Google Places for HVAC businesses in the cities you list.
  2. Checks whether each one ACTUALLY has a working website (opens the link).
  3. Scores each lead 0-100 with a fixed rubric (site need + reviews + rating).
  4. Saves everything to leads.csv, best leads first.

How to run:
    python simple_scraper.py

Edit the CITIES and MAX_LEADS settings just below to change what it searches.
Your keys live in .env (GOOGLE_MAPS_API_KEY and OPENAI_API_KEY).
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# SETTINGS — change these, nothing else needed
# ---------------------------------------------------------------------------

CITIES = [
    "Stuart, FL",
    "Port St. Lucie, FL",
    "Vero Beach, FL",
    "Fort Pierce, FL",
]

SEARCH_TERMS = ["HVAC contractor", "air conditioning repair"]

MAX_LEADS = 20          # how many high-quality leads to deliver
SCAN_POOL = 100         # businesses to scan before narrowing down
MIN_SCORE = 60          # only deliver leads at or above this score
MIN_REVIEWS = 3         # skip businesses with fewer reviews than this
USE_OPENAI = False      # scoring uses the rubric below (fast + consistent)

# Scoring rubric (max 100):
#   Dead website (broken link on Google)   55 pts
#   No website                             44 pts
#   Reviews                                0-20 pts
#   Rating                                 0-15 pts
#   Business legitimacy                    0-15 pts

# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
OUTPUT_CSV = HERE / "leads.csv"

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.displayName,places.nationalPhoneNumber,places.websiteUri,"
    "places.rating,places.userRatingCount,places.formattedAddress,"
    "places.businessStatus"
)
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
CHECK_WORKERS = 10        # parallel website checks
_SPAM_NAME = re.compile(
    r"(24/7|24 hour|#\d|cheapest|cheap|best price|top rated|call now|free estimate)",
    re.I,
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def load_keys() -> tuple[str, str]:
    load_dotenv(HERE / ".env")
    google = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    openai = os.getenv("OPENAI_API_KEY", "").strip()
    if not google:
        raise RuntimeError(
            "Missing GOOGLE_MAPS_API_KEY — set it in Render environment variables."
        )
    return google, openai


def search_places(query: str, api_key: str, max_pages: int = 2) -> list[dict]:
    """Return business records from Google Places for one query.

    Pages through results (20 per page) so we also reach the less-prominent
    businesses — which is exactly where the no-website shops tend to be.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK + ",nextPageToken",
    }
    out: list[dict] = []
    page_token = None
    for _ in range(max_pages):
        body: dict = {"textQuery": query, "maxResultCount": 20}
        if page_token:
            body["pageToken"] = page_token
        resp = requests.post(PLACES_URL, headers=headers, json=body, timeout=30)
        if not resp.ok:
            print(f"  ! Places error ({resp.status_code}): {resp.text[:120]}")
            break
        data = resp.json()
        out.extend(data.get("places", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)  # Places requires a short wait before the next page
    return out


def _url_variants(url: str) -> list[str]:
    """Return URL plus http/https alternates to try."""
    url = url.strip()
    if not url:
        return []
    variants = [url]
    if url.startswith("https://"):
        variants.append("http://" + url[8:])
    elif url.startswith("http://"):
        variants.append("https://" + url[7:])
    else:
        variants.extend([f"https://{url}", f"http://{url}"])
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _page_looks_live(status: int, body: bytes) -> bool:
    """Decide if a response is a real page (not a hard failure)."""
    if status < 400:
        return True
    # Many hosts block bots with 403/401 but still return a real HTML page.
    if status in (401, 403, 405, 406) and len(body) > 400:
        text = body[:2000].lower()
        if b"<html" in text or b"<!doctype" in text:
            return True
    return False


def _fetch_liveness(url: str) -> bool:
    """GET a URL and decide if it hosts a live site."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(
            url, headers=headers, timeout=10, allow_redirects=True, stream=True,
        )
        chunk = b""
        for part in resp.iter_content(8192):
            chunk += part
            if len(chunk) >= 8192:
                break
        resp.close()
        return _page_looks_live(resp.status_code, chunk)
    except requests.exceptions.SSLError:
        # Bad cert on https — caller may try http variant next.
        return False
    except requests.RequestException:
        return False


def website_works(url: str) -> bool:
    """Return True if the URL appears to host a live website.

    Uses GET (not HEAD — many sites block HEAD), tries http/https variants,
    and treats bot-wall 403 pages with HTML as live.
    """
    for try_url in _url_variants(url):
        if _fetch_liveness(try_url):
            return True
    return False


def _probe_domain(domain: str, phone_digits: str) -> str:
    """Try one guessed domain; return URL if the business phone is on the page."""
    for url in (f"https://{domain}", f"http://{domain}"):
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=3,
                allow_redirects=True,
            )
        except requests.RequestException:
            continue
        if resp.status_code >= 400:
            continue
        if phone_digits in re.sub(r"\D", "", resp.text):
            return resp.url
        break
    return ""


# Generic words in HVAC names that don't help guess a domain.
_GENERIC = {
    "air", "conditioning", "conditioner", "heating", "cooling", "hvac", "ac",
    "llc", "inc", "co", "company", "corp", "services", "service", "the", "and",
    "of", "fl", "florida", "repair", "repairs", "refrigeration", "mechanical",
    "solutions", "systems", "comfort", "climate", "control", "plumbing",
    "electric", "electrical", "heat",
}


def _city_from_address(address: str) -> str:
    """Pull a city token from a Google formatted address for domain guessing."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    skip = {"fl", "florida", "usa", "united", "states"}
    for part in reversed(parts):
        clean = re.sub(r"[^a-z]", "", part.lower())
        if len(clean) >= 3 and clean not in skip and not clean.isdigit():
            return clean
    return ""


def _domain_guesses(name: str, address: str = "") -> list[str]:
    """Build likely web addresses from a business name and city.

    e.g. "Sharkey Air LLC" in Stuart -> sharkey.com, sharkeystuart.com, ...
    """
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 3]
    distinct = [w for w in words if w not in _GENERIC]
    city = _city_from_address(address)

    stems: set[str] = set()
    if distinct:
        stems.add(distinct[0])
        stems.add("".join(distinct))
        if len(distinct) >= 2:
            stems.add("".join(distinct[:2]))
        for suffix in ("air", "ac", "hvac", "heating", "cooling", "comfort"):
            stems.add(distinct[0] + suffix)
        if city:
            stems.add(distinct[0] + city)
            stems.add(city + distinct[0])
            stems.add("".join(distinct[:2]) + city)
    stems.add("".join(words))
    if city and len(city) >= 3:
        stems.add(city + "hvac")
        stems.add(city + "air")

    domains: list[str] = []
    for stem in stems:
        if 3 <= len(stem) <= 30:
            domains.append(stem + ".com")
            domains.append(stem + ".net")
    return domains[:12]


def find_unlinked_website(name: str, phone: str, address: str = "") -> str:
    """Find a website Google DOESN'T know about by guessing the address.

    Probes likely domains in parallel; only counts a hit if the business phone
    appears on the page.
    """
    phone_digits = re.sub(r"\D", "", phone)[-10:]
    if not phone_digits:
        return ""

    domains = _domain_guesses(name, address)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_probe_domain, d, phone_digits) for d in domains]
        for fut in as_completed(futures):
            hit = fut.result()
            if hit:
                return hit
    return ""


def review_points(reviews: int) -> int:
    """Map review count to 0-20 points.

    0-5   = neutral
    5-50  = bonus (ramps up)
    50-150 = max bonus (20)
    150+  = smaller bonus
    300+  = possible penalty
    """
    if reviews <= 5:
        return 8
    if reviews < 50:
        return 8 + int((reviews - 5) / (50 - 5) * 10)
    if reviews <= 150:
        return 20
    if reviews < 300:
        return 20 - int((reviews - 150) / (300 - 150) * 8)
    penalty = min(7, (reviews - 300) // 40)
    return max(5, 12 - penalty)


def rating_points(rating: float | None) -> int:
    """Map star rating to 0-15 points."""
    if rating is None:
        return 4
    r = float(rating)
    if r >= 4.8:
        return 15
    if r >= 4.6:
        return 13
    if r >= 4.4:
        return 11
    if r >= 4.2:
        return 9
    if r >= 4.0:
        return 7
    if r >= 3.7:
        return 5
    if r >= 3.5:
        return 3
    return 1


def legitimacy_points(lead: dict) -> int:
    """Estimate business legitimacy from name and address (0-15)."""
    name = lead.get("name", "")
    low = name.lower()
    pts = 6
    if re.search(r"\b(llc|inc|corp|incorporated|company)\b", low):
        pts += 4
    if "&" in name or " and " in low:
        pts += 2
    addr = lead.get("address", "")
    if addr and re.search(r"\d+\s+\w+", addr):
        pts += 3
    if _SPAM_NAME.search(name):
        pts -= 5
    words = [w for w in re.findall(r"[a-z]+", low) if len(w) >= 3]
    if words:
        generic = sum(1 for w in words if w in _GENERIC)
        if generic >= len(words) * 0.6 and len(words) <= 4:
            pts -= 3
    return max(0, min(15, pts))


def site_opportunity_points(lead: dict) -> int:
    """Dead website scores higher — they already tried online and need a rebuild."""
    status = lead.get("site_status")
    if status == "dead":
        return 55
    if status == "none":
        return 44
    return 0


def compute_lead_score(lead: dict) -> tuple[int, str]:
    """Score a lead 0-100 using the fixed rubric."""
    site = site_opportunity_points(lead)
    rev = review_points(int(lead.get("reviews") or 0))
    rat = rating_points(lead.get("rating"))
    leg = legitimacy_points(lead)
    total = min(100, site + rev + rat + leg)

    if lead.get("site_status") == "none":
        site_label = "No website"
    elif lead.get("site_status") == "dead":
        site_label = "Dead website"
    else:
        site_label = "Site opportunity"

    rating_txt = f"{float(lead['rating']):.1f}" if lead.get("rating") else "?"
    reason = (
        f"{site_label} · {lead['reviews']} reviews · {rating_txt}★ · "
        f"legitimacy {leg}/15"
    )
    return total, reason


def score_all_leads(leads: list[dict]) -> str:
    """Apply rubric then learn from logged call history. Returns learning note."""
    for lead in leads:
        lead["score"], lead["reason"] = compute_lead_score(lead)
    try:
        from learning import apply_learning

        return apply_learning(leads)
    except ImportError:
        return ""


def call_opener(lead: dict) -> str:
    """One-line cold-call opener based on website status."""
    if lead.get("site_status") == "dead":
        return (
            "I tried your website link from Google — it's not loading. "
            "We help HVAC companies get a modern site that actually works."
        )
    return (
        "I noticed you don't have a website on your Google listing — "
        "we build sites for local HVAC companies with hosting included."
    )


def _verify_no_site(lead: dict) -> dict | None:
    """Return lead if confirmed no website, else None."""
    if find_unlinked_website(lead["name"], lead["phone"], lead.get("address", "")):
        return None
    lead["has_website"] = False
    lead["site_status"] = "none"
    return lead


def _verify_dead_site(lead: dict) -> dict | None:
    """Return lead only if Google's website link is truly dead/broken."""
    if website_works(lead["website"]):
        return None
    # Google link may be stale — if they have a working site elsewhere, skip.
    if find_unlinked_website(lead["name"], lead["phone"], lead.get("address", "")):
        return None
    lead["has_website"] = False
    lead["site_status"] = "dead"
    return lead


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def collect_leads(
    cities: list[str],
    max_leads: int = MAX_LEADS,
    pool_size: int = SCAN_POOL,
    min_score: int = MIN_SCORE,
    min_reviews: int = MIN_REVIEWS,
    use_openai: bool = True,
    exclude_phones: set[str] | None = None,
    progress=None,
    opportunities_only: bool = True,
    site_filter: str = "all",
) -> list[dict]:
    """Find HVAC leads and return the best ones as a list of dicts.

    Scans Google Places across the city list, verifies site status, scores
    with the rubric, and returns up to `max_leads` at or above `min_score`.
    Keeps scanning until the target is met or the scan budget is exhausted.
    """
    google_key, _openai_key = load_keys()
    exclude_phones = {normalize_phone(p) for p in (exclude_phones or set()) if normalize_phone(p)}

    def say(msg: str) -> None:
        print(msg)
        if progress is not None:
            progress(msg)

    scan_budget = min(max(pool_size, len(exclude_phones) + max_leads * 12, 120), 500)
    say(f"Searching Google Places (scan budget up to {scan_budget} businesses)...")

    no_link: dict[str, dict] = {}
    with_link: dict[str, dict] = {}
    seen = set(exclude_phones)
    queries = [f"{term} {city}" for city in cities for term in SEARCH_TERMS]
    want_none = site_filter in ("all", "none")
    want_dead = site_filter in ("all", "dead")

    def verify_pool() -> list[dict]:
        opportunities: list[dict] = []
        if want_none:
            candidates = list(no_link.values())
            if candidates:
                say(f"Checking {len(candidates)} businesses for hidden websites...")
                done = 0
                with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
                    futures = {pool.submit(_verify_no_site, lead): lead for lead in candidates}
                    for fut in as_completed(futures):
                        done += 1
                        if done % 5 == 0 or done == len(candidates):
                            say(f"Checked {done}/{len(candidates)} no-website businesses")
                        hit = fut.result()
                        if hit:
                            opportunities.append(hit)
        if want_dead:
            listed = list(with_link.values())
            if listed:
                say(f"Checking {len(listed)} listed websites...")
                done = 0
                with ThreadPoolExecutor(max_workers=CHECK_WORKERS) as pool:
                    futures = {pool.submit(_verify_dead_site, lead): lead for lead in listed}
                    for fut in as_completed(futures):
                        done += 1
                        if done % 10 == 0 or done == len(listed):
                            say(f"Checked {done}/{len(listed)} listed sites")
                        hit = fut.result()
                        if hit:
                            opportunities.append(hit)
        return opportunities

    for query in queries:
        total = len(no_link) + len(with_link)
        if total >= scan_budget:
            break
        say(f"Searching: {query}  ({total}/{scan_budget} scanned)")
        for place in search_places(query, google_key, max_pages=3):
            total = len(no_link) + len(with_link)
            if total >= scan_budget:
                break
            if place.get("businessStatus") not in (None, "OPERATIONAL"):
                continue
            phone = (place.get("nationalPhoneNumber") or "").strip()
            phone_key = normalize_phone(phone)
            if not phone or not phone_key or phone_key in seen:
                continue
            if int(place.get("userRatingCount") or 0) < min_reviews:
                continue
            seen.add(phone_key)
            record = {
                "name": (place.get("displayName") or {}).get("text", "").strip(),
                "phone": phone,
                "website": (place.get("websiteUri") or "").strip(),
                "rating": place.get("rating"),
                "reviews": int(place.get("userRatingCount") or 0),
                "address": (place.get("formattedAddress") or "").strip(),
            }
            (with_link if record["website"] else no_link)[phone] = record
        time.sleep(0.5)

    rows = verify_pool()
    if not rows:
        say("No website opportunities found in this scan — try again or clear history.")
        return []

    say(f"Scoring {len(rows)} opportunities...")
    learn_note = score_all_leads(rows)

    rows.sort(key=lambda x: -x["score"])
    high = [r for r in rows if r["score"] >= min_score]
    picked = high[:max_leads]
    if picked:
        msg = f"Kept {len(picked)} leads scoring {min_score}+ (from {len(rows)} opportunities)"
        if learn_note:
            msg += f" · {learn_note}"
        say(msg)
    else:
        say(f"No leads scored {min_score}+ — try more cities or clear history")
    return picked


def main() -> None:
    try:
        rows = collect_leads(CITIES, max_leads=MAX_LEADS, use_openai=USE_OPENAI)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"\nStep 4 — saving {len(rows)} leads to {OUTPUT_CSV.name}")
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "Score", "Business", "Phone", "Website Status", "Website",
            "Rating", "Reviews", "Reason", "Address",
        ])
        status_label = {"working": "Has site", "dead": "Dead site", "none": "No site"}
        for lead in rows:
            writer.writerow([
                lead["score"],
                lead["name"],
                lead["phone"],
                status_label.get(lead["site_status"], lead["site_status"]),
                lead["website"] or "NONE",
                lead["rating"],
                lead["reviews"],
                lead["reason"],
                lead["address"],
            ])

    print("\nDone! Open leads.csv to see your leads (best first).")


if __name__ == "__main__":
    main()
