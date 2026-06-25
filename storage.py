"""Atlas auto-save — local snapshots + optional GitHub/URL remote sync."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import db
from paths import DATA_ROOT, SNAPSHOT_FILE

SNAPSHOT_VERSION = 1
SYNC_DEBOUNCE_SEC = 20

_LOCK = threading.Lock()
_LAST_LOCAL_SAVE = 0.0
_LAST_REMOTE_SYNC = 0.0
_BOOTSTRAP_DONE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def build_snapshot() -> dict:
    return {
        "version": SNAPSHOT_VERSION,
        "saved_at": _now_iso(),
        "app": "atlas",
        "clients": db.list_clients(),
    }


def apply_snapshot(data: dict) -> None:
    clients = data.get("clients") or []
    if clients:
        db.restore_clients(clients)


def load_local_snapshot() -> dict | None:
    if not SNAPSHOT_FILE.exists():
        return None
    try:
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_local_snapshot() -> None:
    global _LAST_LOCAL_SAVE
    snap = build_snapshot()
    _atomic_write(SNAPSHOT_FILE, json.dumps(snap, indent=2))
    _LAST_LOCAL_SAVE = time.time()


def _github_config() -> tuple[str, str, str] | None:
    token = os.getenv("ATLAS_GITHUB_TOKEN", "").strip()
    repo = os.getenv("ATLAS_GITHUB_REPO", "").strip()
    if not token or not repo:
        return None
    path = os.getenv("ATLAS_GITHUB_PATH", "atlas-snapshot.json").strip()
    return token, repo, path


def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_remote_snapshot() -> dict | None:
    gh = _github_config()
    if gh:
        token, repo, path = gh
        try:
            import requests

            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            resp = requests.get(url, headers=_github_headers(token), timeout=30)
            if resp.status_code == 404:
                return None
            if not resp.ok:
                return None
            content = resp.json().get("content", "")
            raw = base64.b64decode(content).decode("utf-8")
            return json.loads(raw)
        except (ImportError, json.JSONDecodeError, OSError, ValueError):
            return None

    url = os.getenv("ATLAS_BACKUP_URL", "").strip()
    if not url:
        return None
    try:
        import requests

        headers = {}
        tok = os.getenv("ATLAS_BACKUP_TOKEN", "").strip()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.ok:
            return resp.json()
    except ImportError:
        pass
    return None


def push_remote_snapshot(snap: dict) -> bool:
    gh = _github_config()
    body = json.dumps(snap, indent=2)
    if gh:
        token, repo, path = gh
        try:
            import requests

            url = f"https://api.github.com/repos/{repo}/contents/{path}"
            headers = _github_headers(token)
            get_resp = requests.get(url, headers=headers, timeout=30)
            sha = get_resp.json().get("sha") if get_resp.ok else None
            payload = {
                "message": f"Atlas auto-save {_now_iso()[:19]}",
                "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            }
            if sha:
                payload["sha"] = sha
            put = requests.put(url, headers=headers, json=payload, timeout=45)
            return put.ok
        except ImportError:
            return False

    url = os.getenv("ATLAS_BACKUP_URL", "").strip()
    if not url:
        return False
    try:
        import requests

        headers = {"Content-Type": "application/json"}
        tok = os.getenv("ATLAS_BACKUP_TOKEN", "").strip()
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        resp = requests.put(url, headers=headers, data=body, timeout=45)
        return resp.ok
    except ImportError:
        return False


def _remote_sync_worker() -> None:
    global _LAST_REMOTE_SYNC
    snap = build_snapshot()
    if push_remote_snapshot(snap):
        _LAST_REMOTE_SYNC = time.time()


def maybe_sync_remote(force: bool = False) -> None:
    if not _github_config() and not os.getenv("ATLAS_BACKUP_URL", "").strip():
        return
    now = time.time()
    if not force and now - _LAST_REMOTE_SYNC < SYNC_DEBOUNCE_SEC:
        return
    threading.Thread(target=_remote_sync_worker, daemon=True).start()


def after_change(reason: str = "") -> None:
    del reason
    with _LOCK:
        save_local_snapshot()
        maybe_sync_remote()


def bootstrap() -> dict:
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return {"status": "already_bootstrapped"}
    _BOOTSTRAP_DONE = True

    with _LOCK:
        clients = db.list_clients()
        if clients:
            return {
                "status": "ok",
                "source": "local_db",
                "clients": len(clients),
                "remote_configured": bool(_github_config() or os.getenv("ATLAS_BACKUP_URL")),
            }

        local = load_local_snapshot()
        if local and local.get("clients"):
            apply_snapshot(local)
            maybe_sync_remote(force=True)
            return {"status": "restored", "source": "local_snapshot"}

        remote = fetch_remote_snapshot()
        if remote and remote.get("clients"):
            apply_snapshot(remote)
            save_local_snapshot()
            return {"status": "restored", "source": "remote"}

        return {
            "status": "empty",
            "remote_configured": bool(_github_config() or os.getenv("ATLAS_BACKUP_URL")),
        }


def status() -> dict:
    clients = db.list_clients()
    gh = _github_config()
    mtime = None
    if SNAPSHOT_FILE.exists():
        mtime = datetime.fromtimestamp(
            SNAPSHOT_FILE.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {
        "clients_in_db": len(clients),
        "local_snapshot": SNAPSHOT_FILE.exists(),
        "local_snapshot_at": mtime,
        "last_local_save": _LAST_LOCAL_SAVE or None,
        "last_remote_sync": _LAST_REMOTE_SYNC or None,
        "remote": "github" if gh else ("url" if os.getenv("ATLAS_BACKUP_URL") else "none"),
        "data_dir": str(DATA_ROOT),
    }
