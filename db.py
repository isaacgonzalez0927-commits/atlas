"""Atlas V0 — SQLite persistence for client operations."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from paths import DATA_ROOT

DB_PATH = Path(os.getenv("ATLAS_DB_PATH", str(DATA_ROOT / "atlas.db")))

_DB_LOCK = threading.Lock()

ASSET_KEYS = ("logo", "photos", "phone", "email", "services", "about")

CLIENT_STATUSES = ("onboarding", "waiting_on_client", "building", "live")
REQUEST_STATUSES = ("submitted", "in_progress", "complete")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = _conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                business_name TEXT NOT NULL DEFAULT '',
                contact_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                website TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'onboarding',
                date_signed TEXT NOT NULL DEFAULT '',
                assets_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'submitted',
                date_submitted TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_requests_client ON requests(client_id);
            CREATE INDEX IF NOT EXISTS idx_notes_client ON notes(client_id);
            """
        )
        conn.commit()
        conn.close()


def _empty_assets() -> dict:
    return {k: False for k in ASSET_KEYS}


def _parse_assets(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        base = _empty_assets()
        for k in ASSET_KEYS:
            base[k] = bool(data.get(k))
        return base
    except json.JSONDecodeError:
        return _empty_assets()


def _row_to_client(row: sqlite3.Row, requests: list, notes: list) -> dict:
    return {
        "id": row["id"],
        "businessName": row["business_name"],
        "contactName": row["contact_name"],
        "email": row["email"],
        "phone": row["phone"],
        "website": row["website"],
        "status": row["status"],
        "dateSigned": row["date_signed"],
        "assets": _parse_assets(row["assets_json"]),
        "requests": requests,
        "notes": notes,
    }


def _request_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "description": r["description"],
        "status": r["status"],
        "dateSubmitted": r["date_submitted"],
    }


def _note_row(n: sqlite3.Row) -> dict:
    return {
        "id": n["id"],
        "text": n["text"],
        "createdAt": n["created_at"],
        "updatedAt": n["updated_at"],
    }


def list_clients() -> list[dict]:
    with _DB_LOCK:
        conn = _conn()
        rows = conn.execute(
            "SELECT * FROM clients ORDER BY date_signed DESC, business_name ASC"
        ).fetchall()
        out = []
        for row in rows:
            reqs = conn.execute(
                "SELECT * FROM requests WHERE client_id = ? ORDER BY date_submitted DESC",
                (row["id"],),
            ).fetchall()
            notes = conn.execute(
                "SELECT * FROM notes WHERE client_id = ? ORDER BY updated_at DESC",
                (row["id"],),
            ).fetchall()
            out.append(
                _row_to_client(
                    row,
                    [_request_row(r) for r in reqs],
                    [_note_row(n) for n in notes],
                )
            )
        conn.close()
        return out


def get_client(client_id: str) -> dict | None:
    clients = list_clients()
    return next((c for c in clients if c["id"] == client_id), None)


def create_client(data: dict) -> dict:
    cid = data.get("id") or str(uuid.uuid4())
    now = _now_iso()
    assets = data.get("assets") or _empty_assets()
    with _DB_LOCK:
        conn = _conn()
        conn.execute(
            """
            INSERT INTO clients (
                id, business_name, contact_name, email, phone, website,
                status, date_signed, assets_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                data.get("businessName", ""),
                data.get("contactName", ""),
                data.get("email", ""),
                data.get("phone", ""),
                data.get("website", ""),
                data.get("status", "onboarding"),
                data.get("dateSigned", ""),
                json.dumps(assets),
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
    return get_client(cid)  # type: ignore[return-value]


def update_client(client_id: str, data: dict) -> dict | None:
    existing = get_client(client_id)
    if not existing:
        return None
    merged = {**existing, **data, "id": client_id}
    assets = merged.get("assets", existing["assets"])
    with _DB_LOCK:
        conn = _conn()
        conn.execute(
            """
            UPDATE clients SET
                business_name = ?, contact_name = ?, email = ?, phone = ?,
                website = ?, status = ?, date_signed = ?, assets_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                merged.get("businessName", ""),
                merged.get("contactName", ""),
                merged.get("email", ""),
                merged.get("phone", ""),
                merged.get("website", ""),
                merged.get("status", "onboarding"),
                merged.get("dateSigned", ""),
                json.dumps(assets),
                _now_iso(),
                client_id,
            ),
        )
        conn.commit()
        conn.close()
    return get_client(client_id)


def delete_client(client_id: str) -> bool:
    with _DB_LOCK:
        conn = _conn()
        cur = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0


def update_assets(client_id: str, patch: dict) -> dict | None:
    client = get_client(client_id)
    if not client:
        return None
    assets = {**client["assets"], **patch}
    return update_client(client_id, {"assets": assets})


def add_request(client_id: str, data: dict) -> dict | None:
    if not get_client(client_id):
        return None
    rid = data.get("id") or str(uuid.uuid4())
    date_sub = data.get("dateSubmitted") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _DB_LOCK:
        conn = _conn()
        conn.execute(
            """
            INSERT INTO requests (id, client_id, title, description, status, date_submitted)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                client_id,
                data.get("title", ""),
                data.get("description", ""),
                data.get("status", "submitted"),
                date_sub,
            ),
        )
        conn.commit()
        conn.close()
    client = get_client(client_id)
    return next((r for r in client["requests"] if r["id"] == rid), None)  # type: ignore[index]


def update_request(client_id: str, request_id: str, patch: dict) -> dict | None:
    with _DB_LOCK:
        conn = _conn()
        row = conn.execute(
            "SELECT * FROM requests WHERE id = ? AND client_id = ?",
            (request_id, client_id),
        ).fetchone()
        if not row:
            conn.close()
            return None
        merged = {**_request_row(row), **patch}
        conn.execute(
            """
            UPDATE requests SET title = ?, description = ?, status = ?, date_submitted = ?
            WHERE id = ? AND client_id = ?
            """,
            (
                merged["title"],
                merged["description"],
                merged["status"],
                merged.get("dateSubmitted", row["date_submitted"]),
                request_id,
                client_id,
            ),
        )
        conn.commit()
        conn.close()
    client = get_client(client_id)
    return next((r for r in client["requests"] if r["id"] == request_id), None)  # type: ignore[index]


def add_note(client_id: str, text: str) -> dict | None:
    if not get_client(client_id):
        return None
    nid = str(uuid.uuid4())
    now = _now_iso()
    with _DB_LOCK:
        conn = _conn()
        conn.execute(
            "INSERT INTO notes (id, client_id, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (nid, client_id, text, now, now),
        )
        conn.commit()
        conn.close()
    return {"id": nid, "text": text, "createdAt": now, "updatedAt": now}


def update_note(client_id: str, note_id: str, text: str) -> dict | None:
    now = _now_iso()
    with _DB_LOCK:
        conn = _conn()
        cur = conn.execute(
            "UPDATE notes SET text = ?, updated_at = ? WHERE id = ? AND client_id = ?",
            (text, now, note_id, client_id),
        )
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return None
    return {"id": note_id, "text": text, "createdAt": now, "updatedAt": now}


def import_clients(clients: list[dict]) -> int:
    """Bulk import (e.g. localStorage migration). Skips if DB already has clients."""
    if list_clients():
        return 0
    return restore_clients(clients)


def clear_all() -> None:
    with _DB_LOCK:
        conn = _conn()
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM requests")
        conn.execute("DELETE FROM clients")
        conn.commit()
        conn.close()


def _import_single_client(c: dict) -> None:
    cid = c.get("id") or str(uuid.uuid4())
    create_client({**c, "id": cid})
    for r in c.get("requests") or []:
        add_request(cid, r)
    for n in c.get("notes") or []:
        with _DB_LOCK:
            conn = _conn()
            conn.execute(
                "INSERT INTO notes (id, client_id, text, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (
                    n.get("id") or str(uuid.uuid4()),
                    cid,
                    n.get("text", ""),
                    n.get("createdAt") or _now_iso(),
                    n.get("updatedAt") or _now_iso(),
                ),
            )
            conn.commit()
            conn.close()


def restore_clients(clients: list[dict]) -> int:
    """Replace all data with a backup snapshot."""
    clear_all()
    count = 0
    for c in clients:
        _import_single_client(c)
        count += 1
    return count
