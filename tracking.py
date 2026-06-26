"""Central call tracking — SQLite store for all caller outcomes.

Designed for permanent retention and future use by Scraper V3 / Atlas / AI scoring.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

from paths import DATA_ROOT

DB_PATH = DATA_ROOT / "calls.db"

_DB_LOCK = threading.Lock()

OUTCOMES = (
    "no_answer",
    "not_interested",
    "callback",
    "preview",
    "client",
    # legacy Nexus value — still accepted on import
    "interested",
)

OUTCOME_LABELS = {
    "no_answer": "No Answer",
    "not_interested": "Not Interested",
    "callback": "Call Back",
    "preview": "Preview",
    "client": "Client",
    "interested": "Preview",
}

INTEREST_OUTCOMES = {"preview", "callback", "client", "interested"}
CLOSE_OUTCOMES = {"client"}
PREVIEW_OUTCOMES = {"preview", "interested"}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = _conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL,
                caller_id TEXT NOT NULL DEFAULT '',
                business_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                phone_key TEXT NOT NULL,
                score INTEGER,
                site_status TEXT,
                city TEXT,
                address TEXT,
                outcome TEXT NOT NULL,
                notes TEXT DEFAULT '',
                report_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_calls_logged ON calls(logged_at);
            CREATE INDEX IF NOT EXISTS idx_calls_outcome ON calls(outcome);
            CREATE INDEX IF NOT EXISTS idx_calls_city ON calls(city);
            CREATE INDEX IF NOT EXISTS idx_calls_site ON calls(site_status);
            CREATE INDEX IF NOT EXISTS idx_calls_phone ON calls(phone_key);

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_number INTEGER NOT NULL UNIQUE,
                call_range_start INTEGER NOT NULL,
                call_range_end INTEGER NOT NULL,
                generated_at TEXT NOT NULL,
                total_calls INTEGER NOT NULL,
                interested INTEGER NOT NULL,
                callbacks INTEGER NOT NULL,
                clients INTEGER NOT NULL,
                interest_rate REAL NOT NULL,
                close_rate REAL NOT NULL,
                dead_calls INTEGER NOT NULL,
                dead_clients INTEGER NOT NULL,
                no_calls INTEGER NOT NULL,
                no_clients INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()


def city_from_address(address: str) -> str:
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",")]
    skip = {"fl", "florida", "usa", "united states"}
    for part in reversed(parts):
        low = part.lower()
        if low in skip or re.match(r"^\d{5}", part.strip()):
            continue
        if re.search(r"\b[A-Z]{2}\b", part) and len(part.strip()) <= 4:
            continue
        return part.strip()
    return parts[0] if parts else ""


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def log_call(
    *,
    caller_id: str,
    business_name: str,
    phone: str,
    score: int | None,
    site_status: str,
    address: str,
    outcome: str,
    notes: str = "",
) -> dict:
    """Log one call outcome. Auto-generates a report every 100 calls."""
    outcome = outcome.lower().strip()
    if outcome == "interested":
        outcome = "preview"
    if outcome not in OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome}")

    phone_key = normalize_phone(phone)
    city = city_from_address(address)
    now = datetime.now(timezone.utc).isoformat()

    with _DB_LOCK:
        conn = _conn()
        cur = conn.execute(
            """
            INSERT INTO calls (
                logged_at, caller_id, business_name, phone, phone_key,
                score, site_status, city, address, outcome, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now, caller_id or "caller", business_name, phone, phone_key,
                score, site_status, city, address, outcome, notes,
            ),
        )
        call_id = cur.lastrowid
        total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        conn.commit()

        report = None
        if total % 100 == 0:
            report = _generate_report(conn, total)
        conn.close()

    try:
        import storage

        storage.after_change("log_call")
    except ImportError:
        pass

    return {"id": call_id, "total_calls": total, "report": report}


def _generate_report(conn: sqlite3.Connection, total: int) -> dict:
    """Build and save a report for the latest block of 100 calls."""
    report_number = total // 100

    rows = conn.execute(
        "SELECT * FROM calls ORDER BY id DESC LIMIT 100"
    ).fetchall()
    rows = list(reversed(rows))

    start_id = rows[0]["id"] if rows else total - 99
    end_id = rows[-1]["id"] if rows else total

    stats = _stats_from_rows(rows)
    snapshot = {
        "calls": [dict(r) for r in rows],
        "stats": stats,
    }
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO reports (
            report_number, call_range_start, call_range_end, generated_at,
            total_calls, interested, callbacks, clients,
            interest_rate, close_rate,
            dead_calls, dead_clients, no_calls, no_clients,
            snapshot_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report_number,
            start_id,
            end_id,
            now,
            stats["total"],
            stats["interested"],
            stats["callbacks"],
            stats["clients"],
            stats["interest_rate"],
            stats["close_rate"],
            stats["dead_calls"],
            stats["dead_clients"],
            stats["no_calls"],
            stats["no_clients"],
            json.dumps(snapshot),
        ),
    )
    report_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "UPDATE calls SET report_id = ? WHERE id IN "
        "(SELECT id FROM calls ORDER BY id DESC LIMIT 100)",
        (report_id,),
    )
    conn.commit()
    return get_report(report_number)


def _stats_from_rows(rows: list[sqlite3.Row]) -> dict:
    total = len(rows)
    interested = sum(1 for r in rows if r["outcome"] in INTEREST_OUTCOMES)
    previews = sum(1 for r in rows if r["outcome"] in PREVIEW_OUTCOMES)
    callbacks = sum(1 for r in rows if r["outcome"] == "callback")
    clients = sum(1 for r in rows if r["outcome"] == "client")
    dead = [r for r in rows if r["site_status"] == "dead"]
    none = [r for r in rows if r["site_status"] == "none"]
    dead_clients = sum(1 for r in dead if r["outcome"] == "client")
    no_clients = sum(1 for r in none if r["outcome"] == "client")

    return {
        "total": total,
        "interested": interested,
        "previews": previews,
        "callbacks": callbacks,
        "clients": clients,
        "interest_rate": round(interested / total * 100, 1) if total else 0,
        "close_rate": round(clients / total * 100, 1) if total else 0,
        "dead_calls": len(dead),
        "dead_clients": dead_clients,
        "no_calls": len(none),
        "no_clients": no_clients,
        "dead_close_rate": round(dead_clients / len(dead) * 100, 1) if dead else 0,
        "no_close_rate": round(no_clients / len(none) * 100, 1) if none else 0,
    }


def dashboard_stats() -> dict:
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM calls ORDER BY id DESC").fetchall()
        recent = conn.execute(
            "SELECT * FROM calls ORDER BY id DESC LIMIT 25"
        ).fetchall()
        conn.close()

    stats = _stats_from_rows(rows)
    city_counts: dict[str, dict] = {}
    for r in rows:
        c = r["city"] or "Unknown"
        if c not in city_counts:
            city_counts[c] = {"calls": 0, "interested": 0, "clients": 0}
        city_counts[c]["calls"] += 1
        if r["outcome"] in INTEREST_OUTCOMES:
            city_counts[c]["interested"] += 1
        if r["outcome"] == "client":
            city_counts[c]["clients"] += 1

    top_cities = sorted(
        city_counts.items(),
        key=lambda x: (x[1]["clients"], x[1]["interested"]),
        reverse=True,
    )[:10]

    dead_rows = [r for r in rows if r["site_status"] == "dead"]
    none_rows = [r for r in rows if r["site_status"] == "none"]
    dead_stats = _stats_from_rows(dead_rows)
    none_stats = _stats_from_rows(none_rows)

    return {
        **stats,
        "dead_interest_rate": dead_stats["interest_rate"],
        "dead_close_rate": dead_stats["close_rate"],
        "no_interest_rate": none_stats["interest_rate"],
        "no_close_rate": none_stats["close_rate"],
        "top_cities": [
            {"city": c, **data} for c, data in top_cities
        ],
        "recent": [_row_to_dict(r) for r in recent],
    }


def get_all_reports() -> list[dict]:
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY report_number DESC"
        ).fetchall()
        conn.close()
    return [_report_row(r) for r in rows]


def get_report(report_number: int) -> dict:
    with _DB_LOCK:
        conn = _conn()
        row = conn.execute(
            "SELECT * FROM reports WHERE report_number = ?", (report_number,)
        ).fetchone()
        conn.close()
    if not row:
        return {}
    return _report_row(row)


def call_history(
    *,
    site_status: str = "",
    outcome: str = "",
    city: str = "",
    limit: int = 500,
) -> list[dict]:
    query = "SELECT * FROM calls WHERE 1=1"
    params: list = []
    if site_status in ("dead", "none"):
        query += " AND site_status = ?"
        params.append(site_status)
    if outcome and outcome in OUTCOMES:
        query += " AND outcome = ?"
        params.append(outcome)
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute(query, params).fetchall()
        conn.close()
    return [_row_to_dict(r) for r in rows]


def statistics_page() -> dict:
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM calls").fetchall()
        conn.close()

    city_data: dict[str, dict] = {}
    for r in rows:
        c = r["city"] or "Unknown"
        if c not in city_data:
            city_data[c] = {
                "calls": 0, "interested": 0, "clients": 0, "scores_interested": [],
                "scores_client": [],
            }
        city_data[c]["calls"] += 1
        if r["outcome"] in INTEREST_OUTCOMES:
            city_data[c]["interested"] += 1
            if r["score"] is not None:
                city_data[c]["scores_interested"].append(r["score"])
        if r["outcome"] == "client":
            city_data[c]["clients"] += 1
            if r["score"] is not None:
                city_data[c]["scores_client"].append(r["score"])

    def rate(items, key_num, key_den):
        return sorted(
            [
                {
                    "city": c,
                    "calls": d["calls"],
                    "rate": round(d[key_num] / d[key_den] * 100, 1)
                    if d[key_den] else 0,
                }
                for c, d in items
                if d[key_den] >= 3
            ],
            key=lambda x: x["rate"],
            reverse=True,
        )[:10]

    items = city_data.items()
    top_interest = rate(items, "interested", "calls")
    top_close = rate(items, "clients", "calls")

    interested_scores = [
        r["score"] for r in rows
        if r["outcome"] in INTEREST_OUTCOMES and r["score"] is not None
    ]
    client_scores = [
        r["score"] for r in rows
        if r["outcome"] == "client" and r["score"] is not None
    ]

    dead = [r for r in rows if r["site_status"] == "dead"]
    none = [r for r in rows if r["site_status"] == "none"]
    dead_s = _stats_from_rows(dead)
    none_s = _stats_from_rows(none)

    return {
        "top_cities_interest": top_interest,
        "top_cities_close": top_close,
        "avg_score_interested": round(
            sum(interested_scores) / len(interested_scores), 1
        ) if interested_scores else 0,
        "avg_score_client": round(
            sum(client_scores) / len(client_scores), 1
        ) if client_scores else 0,
        "dead_conversion": dead_s["close_rate"],
        "no_conversion": none_s["close_rate"],
        "dead_interest": dead_s["interest_rate"],
        "no_interest": none_s["interest_rate"],
        "total_calls": len(rows),
    }


def latest_outcomes_by_phone() -> dict[str, dict]:
    """Most recent logged outcome per phone key."""
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY id DESC"
        ).fetchall()
        conn.close()
    by_phone: dict[str, dict] = {}
    for row in rows:
        key = row["phone_key"]
        if key and key not in by_phone:
            by_phone[key] = _row_to_dict(row)
    return by_phone


def all_calls_raw() -> list[dict]:
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute("SELECT * FROM calls ORDER BY id").fetchall()
        conn.close()
    return [dict(r) for r in rows]


def export_backup() -> dict:
    """Full backup of calls + reports for download."""
    with _DB_LOCK:
        conn = _conn()
        calls = [dict(r) for r in conn.execute("SELECT * FROM calls ORDER BY id").fetchall()]
        reports = [dict(r) for r in conn.execute("SELECT * FROM reports ORDER BY id").fetchall()]
        conn.close()
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "calls": calls,
        "reports": reports,
    }


def restore_backup(payload: dict) -> dict:
    """Replace all call data from a backup file."""
    calls = payload.get("calls") or []
    reports = payload.get("reports") or []
    with _DB_LOCK:
        conn = _conn()
        conn.execute("DELETE FROM calls")
        conn.execute("DELETE FROM reports")
        for row in calls:
            conn.execute(
                """
                INSERT INTO calls (
                    logged_at, caller_id, business_name, phone, phone_key,
                    score, site_status, city, address, outcome, notes, report_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("logged_at"),
                    row.get("caller_id", ""),
                    row.get("business_name", ""),
                    row.get("phone", ""),
                    row.get("phone_key", ""),
                    row.get("score"),
                    row.get("site_status", ""),
                    row.get("city", ""),
                    row.get("address", ""),
                    row.get("outcome", ""),
                    row.get("notes", ""),
                    row.get("report_id"),
                ),
            )
        for row in reports:
            conn.execute(
                """
                INSERT INTO reports (
                    report_number, call_range_start, call_range_end,
                    generated_at, total_calls, interested, callbacks, clients,
                    interest_rate, close_rate, dead_calls, dead_clients,
                    no_calls, no_clients, snapshot_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("report_number"),
                    row.get("call_range_start"),
                    row.get("call_range_end"),
                    row.get("generated_at"),
                    row.get("total_calls"),
                    row.get("interested"),
                    row.get("callbacks"),
                    row.get("clients"),
                    row.get("interest_rate"),
                    row.get("close_rate"),
                    row.get("dead_calls"),
                    row.get("dead_clients"),
                    row.get("no_calls"),
                    row.get("no_clients"),
                    row.get("snapshot_json", "{}"),
                ),
            )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        conn.close()
    try:
        import storage

        storage.after_change("restore")
    except ImportError:
        pass
    return {"restored_calls": total, "restored_reports": len(reports)}


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["lead_type"] = (
        "Dead Website" if d.get("site_status") == "dead"
        else "No Website" if d.get("site_status") == "none"
        else d.get("site_status", "")
    )
    d["outcome_label"] = OUTCOME_LABELS.get(d.get("outcome", ""), d.get("outcome", ""))
    d["date_called"] = (d.get("logged_at") or "")[:10]
    return d


def _report_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    snap = json.loads(d.get("snapshot_json") or "{}")
    d["top_cities"] = snap.get("stats", {}).get("top_cities", [])
    d["label"] = (
        f"Report #{d['report_number']} "
        f"(Calls {d['call_range_start']}-{d['call_range_end']})"
    )
    return d


init_db()
