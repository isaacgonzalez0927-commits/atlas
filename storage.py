"""Atlas auto-save — unified snapshot (clients + leads + learning data)."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import db
import tracking
from paths import DATA_ROOT, HISTORY_FILE, LEARN_CACHE_FILE, SNAPSHOT_FILE

SNAPSHOT_VERSION = 2
SYNC_DEBOUNCE_SEC = 20
PERIODIC_SAVE_SEC = 180
REMOTE_RETRIES = 5
RECOVERY_POLL_SEC = 60
_LAST_BOOTSTRAP: dict = {}
_RECOVERY_STARTED = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_LOCK = threading.Lock()
_LAST_LOCAL_SAVE = 0.0
_LAST_REMOTE_SYNC = 0.0
_BOOTSTRAP_DONE = False


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _read_json_file(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def build_snapshot() -> dict:
    snap = tracking.export_backup()
    snap["version"] = SNAPSHOT_VERSION
    snap["saved_at"] = _now_iso()
    snap["app"] = "atlas"
    snap["clients"] = db.list_clients()
    hist = _read_json_file(HISTORY_FILE)
    snap["generated_history"] = hist if hist else {"phone_keys": []}
    cache = _read_json_file(LEARN_CACHE_FILE)
    if cache:
        snap["learn_cache"] = cache
    return snap


def _has_data(snap: dict) -> bool:
    if snap.get("clients"):
        return True
    if snap.get("calls"):
        return True
    hist = snap.get("generated_history") or {}
    return bool(hist.get("phone_keys"))


def apply_snapshot(data: dict) -> None:
    clients = data.get("clients") or []
    if clients:
        db.restore_clients(clients)

    calls = data.get("calls")
    if calls is not None:
        tracking.restore_backup({
            "calls": calls,
            "reports": data.get("reports") or [],
        })

    hist = data.get("generated_history")
    if isinstance(hist, dict):
        _atomic_write(HISTORY_FILE, json.dumps(hist, indent=2))

    cache = data.get("learn_cache")
    if isinstance(cache, dict):
        _atomic_write(LEARN_CACHE_FILE, json.dumps(cache, indent=2))


def load_local_snapshot() -> dict | None:
    return _read_json_file(SNAPSHOT_FILE)


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


def _fetch_remote_once() -> dict | None:
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


def fetch_remote_snapshot() -> dict | None:
    for attempt in range(REMOTE_RETRIES):
        snap = _fetch_remote_once()
        if snap is not None:
            return snap
        if attempt < REMOTE_RETRIES - 1:
            time.sleep(2 * (attempt + 1))
    return None


def push_remote_snapshot(snap: dict) -> bool:
    if not _has_data(snap):
        return False

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
    snap = build_snapshot()
    if not _has_data(snap):
        return
    now = time.time()
    if not force and now - _LAST_REMOTE_SYNC < SYNC_DEBOUNCE_SEC:
        return
    threading.Thread(target=_remote_sync_worker, daemon=True).start()


def after_change(reason: str = "") -> None:
    del reason
    snap = build_snapshot()
    if not _has_data(snap):
        return
    with _LOCK:
        _atomic_write(SNAPSHOT_FILE, json.dumps(snap, indent=2))
        global _LAST_LOCAL_SAVE
        _LAST_LOCAL_SAVE = time.time()
        maybe_sync_remote()


def _local_has_data() -> bool:
    if db.list_clients():
        return True
    try:
        with tracking._DB_LOCK:
            conn = tracking._conn()
            count = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            conn.close()
        if count > 0:
            return True
    except OSError:
        pass
    hist = _read_json_file(HISTORY_FILE)
    return bool(hist and hist.get("phone_keys"))


def bootstrap() -> dict:
    global _BOOTSTRAP_DONE, _LAST_BOOTSTRAP
    if _BOOTSTRAP_DONE:
        return _LAST_BOOTSTRAP or {"status": "already_bootstrapped"}
    _BOOTSTRAP_DONE = True

    with _LOCK:
        if _local_has_data():
            save_local_snapshot()
            maybe_sync_remote(force=True)
            _LAST_BOOTSTRAP = {
                "status": "ok",
                "source": "local_db",
                "clients": len(db.list_clients()),
                "remote_configured": bool(_github_config() or os.getenv("ATLAS_BACKUP_URL")),
            }
            return _LAST_BOOTSTRAP

        local = load_local_snapshot()
        if local and _has_data(local):
            apply_snapshot(local)
            save_local_snapshot()
            maybe_sync_remote(force=True)
            _LAST_BOOTSTRAP = {
                "status": "restored",
                "source": "local_snapshot",
                "clients": len(local.get("clients") or []),
                "calls": len(local.get("calls") or []),
            }
            return _LAST_BOOTSTRAP

        remote = fetch_remote_snapshot()
        if remote and _has_data(remote):
            apply_snapshot(remote)
            save_local_snapshot()
            maybe_sync_remote(force=True)
            _LAST_BOOTSTRAP = {
                "status": "restored",
                "source": "remote",
                "clients": len(remote.get("clients") or []),
                "calls": len(remote.get("calls") or []),
            }
            return _LAST_BOOTSTRAP

        _LAST_BOOTSTRAP = {
            "status": "empty",
            "remote_configured": bool(_github_config() or os.getenv("ATLAS_BACKUP_URL")),
        }
        return _LAST_BOOTSTRAP


def start_periodic_save() -> None:
    def _loop() -> None:
        while True:
            time.sleep(PERIODIC_SAVE_SEC)
            try:
                snap = build_snapshot()
                if _has_data(snap):
                    with _LOCK:
                        _atomic_write(SNAPSHOT_FILE, json.dumps(snap, indent=2))
                    maybe_sync_remote(force=True)
            except Exception:
                pass

    threading.Thread(target=_loop, daemon=True, name="atlas-periodic-save").start()


def start_recovery_loop() -> None:
    global _RECOVERY_STARTED
    if _RECOVERY_STARTED:
        return
    if not _github_config() and not os.getenv("ATLAS_BACKUP_URL", "").strip():
        return
    _RECOVERY_STARTED = True

    def _loop() -> None:
        global _LAST_BOOTSTRAP
        while True:
            time.sleep(RECOVERY_POLL_SEC)
            try:
                if _local_has_data():
                    return
                remote = fetch_remote_snapshot()
                if not remote or not _has_data(remote):
                    continue
                with _LOCK:
                    if _local_has_data():
                        return
                    apply_snapshot(remote)
                    save_local_snapshot()
                    _LAST_BOOTSTRAP = {
                        "status": "restored",
                        "source": "recovery_loop",
                        "clients": len(remote.get("clients") or []),
                        "calls": len(remote.get("calls") or []),
                    }
                print(f"[atlas] storage recovery: {_LAST_BOOTSTRAP}", flush=True)
                return
            except Exception:
                pass

    threading.Thread(target=_loop, daemon=True, name="atlas-recovery").start()


def status() -> dict:
    clients = db.list_clients()
    try:
        with tracking._DB_LOCK:
            conn = tracking._conn()
            calls = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
            conn.close()
    except OSError:
        calls = 0
    gh = _github_config()
    mtime = None
    if SNAPSHOT_FILE.exists():
        mtime = datetime.fromtimestamp(
            SNAPSHOT_FILE.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    return {
        "clients_in_db": len(clients),
        "calls_in_db": calls,
        "local_snapshot": SNAPSHOT_FILE.exists(),
        "local_snapshot_at": mtime,
        "last_local_save": _LAST_LOCAL_SAVE or None,
        "last_remote_sync": _LAST_REMOTE_SYNC or None,
        "last_bootstrap": _LAST_BOOTSTRAP,
        "remote": "github" if gh else ("url" if os.getenv("ATLAS_BACKUP_URL") else "none"),
        "data_dir": str(DATA_ROOT),
    }
