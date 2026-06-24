"""Atlas V0 — Flask API + static frontend (Ascend client OS)."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import db

HERE = Path(__file__).parent
ATLAS_CODE = os.getenv("ATLAS_CODE", "").strip()

app = Flask(__name__, static_folder=str(HERE), static_url_path="")


def _auth_ok() -> bool:
    if not ATLAS_CODE:
        return True
    supplied = (request.headers.get("X-Atlas-Code") or "").strip()
    if not supplied and request.is_json:
        supplied = (request.json or {}).get("code", "").strip()
    return supplied == ATLAS_CODE


def _require_auth():
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.before_request
def init_db_once():
    if not getattr(app, "_db_ready", False):
        db.init_db()
        app._db_ready = True


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "auth_required": bool(ATLAS_CODE),
    })


@app.get("/api/clients")
def api_list_clients():
    err = _require_auth()
    if err:
        return err
    return jsonify(db.list_clients())


@app.get("/api/clients/<client_id>")
def api_get_client(client_id: str):
    err = _require_auth()
    if err:
        return err
    client = db.get_client(client_id)
    if not client:
        return jsonify({"error": "not_found"}), 404
    return jsonify(client)


@app.post("/api/clients")
def api_create_client():
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not (data.get("businessName") or "").strip():
        return jsonify({"error": "business_name_required"}), 400
    return jsonify(db.create_client(data)), 201


@app.put("/api/clients/<client_id>")
def api_update_client(client_id: str):
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    client = db.update_client(client_id, data)
    if not client:
        return jsonify({"error": "not_found"}), 404
    return jsonify(client)


@app.delete("/api/clients/<client_id>")
def api_delete_client(client_id: str):
    err = _require_auth()
    if err:
        return err
    if not db.delete_client(client_id):
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


@app.patch("/api/clients/<client_id>/assets")
def api_update_assets(client_id: str):
    err = _require_auth()
    if err:
        return err
    patch = request.get_json(silent=True) or {}
    client = db.update_assets(client_id, patch)
    if not client:
        return jsonify({"error": "not_found"}), 404
    return jsonify(client)


@app.post("/api/clients/<client_id>/requests")
def api_add_request(client_id: str):
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    if not (data.get("title") or "").strip():
        return jsonify({"error": "title_required"}), 400
    item = db.add_request(client_id, data)
    if not item:
        return jsonify({"error": "not_found"}), 404
    return jsonify(item), 201


@app.put("/api/clients/<client_id>/requests/<request_id>")
def api_update_request(client_id: str, request_id: str):
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    item = db.update_request(client_id, request_id, data)
    if not item:
        return jsonify({"error": "not_found"}), 404
    return jsonify(item)


@app.post("/api/clients/<client_id>/notes")
def api_add_note(client_id: str):
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text_required"}), 400
    note = db.add_note(client_id, text)
    if not note:
        return jsonify({"error": "not_found"}), 404
    return jsonify(note), 201


@app.put("/api/clients/<client_id>/notes/<note_id>")
def api_update_note(client_id: str, note_id: str):
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text_required"}), 400
    note = db.update_note(client_id, note_id, text)
    if not note:
        return jsonify({"error": "not_found"}), 404
    return jsonify(note)


@app.post("/api/migrate")
def api_migrate():
    """One-time import from browser localStorage."""
    err = _require_auth()
    if err:
        return err
    if db.list_clients():
        return jsonify({"error": "already_has_data"}), 409
    payload = request.get_json(silent=True) or {}
    clients = payload.get("clients") or []
    count = db.import_clients(clients)
    return jsonify({"ok": True, "imported": count})


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/<path:path>")
def static_files(path: str):
    full = HERE / path
    if full.is_file():
        return send_from_directory(HERE, path)
    return send_from_directory(HERE, "index.html")


if __name__ == "__main__":
    db.init_db()
    port = int(os.getenv("PORT", "5001"))
    print(f"Atlas V0 — http://localhost:{port}")
    if ATLAS_CODE:
        print("  Access code: ENABLED (ATLAS_CODE set)")
    else:
        print("  Access code: OFF (set ATLAS_CODE in production)")
    app.run(host="0.0.0.0", port=port, debug=True)
