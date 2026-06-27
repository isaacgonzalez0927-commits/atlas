"""Atlas — unified Ascend operating system (clients + leads)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import db
import leads_engine
import storage
import tracking
from atlas_icons import ATLAS_MANIFEST_ICONS
from learning import learning_status

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
ATLAS_CODE = os.getenv("ATLAS_CODE", "").strip()
CALLER_NAME = os.getenv("CALLER_NAME", "sebastien").strip()

app = Flask(__name__, static_folder=str(HERE), static_url_path="")

# Restore + periodic save at worker startup (not only first browser request).
db.init_db()
tracking.init_db()
_boot = storage.bootstrap()
storage.start_periodic_save()
storage.start_recovery_loop()
print(f"[atlas] storage bootstrap: {_boot}", flush=True)


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
        app._db_ready = True


@app.after_request
def auto_save_after_api(response):
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and request.path.startswith("/api/")
        and response.status_code < 400
        and request.path not in ("/api/health", "/api/auth/verify", "/api/migrate")
    ):
        storage.after_change(request.path)
    return response


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "auth_required": bool(ATLAS_CODE),
        "google_maps_configured": bool(os.getenv("GOOGLE_MAPS_API_KEY", "").strip()),
    })


@app.get("/api/dashboard")
def api_dashboard():
    err = _require_auth()
    if err:
        return err
    clients = db.list_clients()
    lead_stats = tracking.dashboard_stats()
    requests_open = sum(
        1 for c in clients for r in (c.get("requests") or [])
        if r.get("status") != "complete"
    )
    active_clients = sum(
        1 for c in clients if c.get("status") in ("onboarding", "building", "waiting_on_client")
    )
    total_leads = lead_stats.get("total", 0)
    called = total_leads
    previews = lead_stats.get("previews", 0)
    clients_won = lead_stats.get("clients", 0)
    conversion = round(clients_won / called * 100, 1) if called else 0

    return jsonify({
        "clients": {
            "total": len(clients),
            "active": active_clients,
            "open_requests": requests_open,
        },
        "leads": {
            "total": total_leads,
            "called": called,
            "previews": previews,
            "clients": clients_won,
            "conversion_rate": conversion,
            "callbacks": lead_stats.get("callbacks", 0),
            "interest_rate": lead_stats.get("interest_rate", 0),
        },
        "recent_calls": lead_stats.get("recent", [])[:8],
        "learning": learning_status(),
        "storage": storage.status(),
    })


# ---------------------------------------------------------------------------
# Leads (Nexus engine)
# ---------------------------------------------------------------------------


@app.get("/api/leads/cities")
def api_leads_cities():
    err = _require_auth()
    if err:
        return err
    return jsonify(leads_engine.florida_cities_list())


@app.post("/api/leads/generate")
def api_leads_generate():
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    rate_key = f"{request.remote_addr}:{request.headers.get('X-Atlas-Code', '')}"
    job_id, error = leads_engine.start_generation(
        mode=data.get("mode", "random"),
        city=(data.get("city") or "").strip(),
        count=int(data.get("count", 20)),
        site_filter=data.get("site_filter", "all"),
        industry=(data.get("industry") or "hvac").strip(),
        exclude_phones=data.get("exclude_phones") or [],
        rate_key=rate_key,
    )
    if error:
        code = 503 if error.get("error") == "missing_api_key" else 429
        return jsonify(error), code
    return jsonify({"job_id": job_id})


@app.get("/api/leads/status/<job_id>")
def api_leads_status(job_id: str):
    err = _require_auth()
    if err:
        return err
    job = leads_engine.get_job(job_id)
    if not job:
        return jsonify({"status": "unknown"}), 404
    return jsonify(job)


@app.get("/api/leads/outcomes")
def api_leads_outcomes():
    err = _require_auth()
    if err:
        return err
    return jsonify({
        "outcomes": [
            {"value": "", "label": "Not Called"},
            {"value": "no_answer", "label": "No Answer"},
            {"value": "not_interested", "label": "Not Interested"},
            {"value": "callback", "label": "Call Back"},
            {"value": "preview", "label": "Preview"},
            {"value": "client", "label": "Client"},
        ],
        "by_phone": tracking.latest_outcomes_by_phone(),
    })


@app.post("/api/leads/log-outcome")
def api_leads_log_outcome():
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    outcome = (data.get("outcome") or "").strip().lower()
    if not outcome:
        return jsonify({"error": "outcome_required"}), 400
    try:
        result = tracking.log_call(
            caller_id=CALLER_NAME,
            business_name=data.get("business_name", ""),
            phone=data.get("phone", ""),
            score=data.get("score"),
            site_status=data.get("site_status", ""),
            address=data.get("address", ""),
            outcome=outcome,
            notes=data.get("notes", ""),
        )
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/leads/convert-to-client")
def api_leads_convert():
    err = _require_auth()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    name = (data.get("business_name") or data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not name:
        return jsonify({"error": "business_name_required"}), 400

    client = db.create_client({
        "businessName": name,
        "phone": phone,
        "website": data.get("website", ""),
        "status": "onboarding",
        "dateSigned": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    })

    try:
        tracking.log_call(
            caller_id=CALLER_NAME,
            business_name=name,
            phone=phone,
            score=data.get("score"),
            site_status=data.get("site_status", ""),
            address=data.get("address", ""),
            outcome="client",
            notes="Converted from lead",
        )
    except ValueError:
        pass

    return jsonify({"ok": True, "client": client}), 201


@app.get("/api/leads/history")
def api_leads_history():
    err = _require_auth()
    if err:
        return err
    return jsonify(tracking.call_history(
        site_status=request.args.get("site_status", ""),
        outcome=request.args.get("outcome", ""),
        city=request.args.get("city", ""),
    ))


@app.get("/api/leads/reports")
def api_leads_reports():
    err = _require_auth()
    if err:
        return err
    return jsonify(tracking.get_all_reports())


@app.get("/api/leads/stats")
def api_leads_stats():
    err = _require_auth()
    if err:
        return err
    return jsonify(tracking.statistics_page())


@app.get("/api/leads/learning")
def api_leads_learning():
    err = _require_auth()
    if err:
        return err
    return jsonify(learning_status())


@app.post("/api/leads/reset-history")
def api_leads_reset_history():
    err = _require_auth()
    if err:
        return err
    from paths import HISTORY_FILE

    HISTORY_FILE.write_text('{"phone_keys": []}', encoding="utf-8")
    storage.after_change("reset_history")
    return jsonify({"ok": True})


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


@app.get("/api/storage")
def api_storage():
    err = _require_auth()
    if err:
        return err
    return jsonify(storage.status())


@app.get("/api/export")
def api_export():
    err = _require_auth()
    if err:
        return err

    snap = storage.build_snapshot()
    return jsonify({
        "version": snap.get("version", 2),
        "exportedAt": datetime.now(timezone.utc).isoformat(),
        "clients": snap.get("clients") or [],
        "calls": snap.get("calls") or [],
        "reports": snap.get("reports") or [],
        "generated_history": snap.get("generated_history") or {"phone_keys": []},
        "learn_cache": snap.get("learn_cache"),
    })


@app.post("/api/restore")
def api_restore():
    """Restore from a backup file (replaces all current data)."""
    err = _require_auth()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    clients = payload.get("clients") or []
    calls = payload.get("calls")
    if not clients and calls is None:
        return jsonify({"error": "no_data"}), 400
    if clients:
        db.restore_clients(clients)
    if calls is not None:
        tracking.restore_backup({
            "calls": calls,
            "reports": payload.get("reports") or [],
        })
    hist = payload.get("generated_history")
    if isinstance(hist, dict):
        from paths import HISTORY_FILE

        HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    storage.after_change("restore")
    return jsonify({
        "ok": True,
        "restored_clients": len(clients),
        "restored_calls": len(calls or []),
    })


@app.get("/manifest.webmanifest")
def manifest():
    return jsonify({
        "name": "Atlas",
        "short_name": "Atlas",
        "description": "Ascend operating system — clients, leads, and operations",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#f6f9fc",
        "theme_color": "#0a2540",
        "icons": ATLAS_MANIFEST_ICONS,
    })


@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    pref = (request.headers.get("Sec-CH-Prefers-Color-Scheme") or "").lower()
    name = "static/apple-touch-icon-dark.png" if pref == "dark" else "static/apple-touch-icon-light.png"
    return send_from_directory(HERE, name)


@app.get("/favicon.ico")
def favicon():
    pref = (request.headers.get("Sec-CH-Prefers-Color-Scheme") or "").lower()
    name = "static/icon-192-dark.png" if pref == "dark" else "static/icon-192-light.png"
    return send_from_directory(HERE, name)


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
