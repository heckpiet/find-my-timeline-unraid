"""Flask web application for viewing location history and managing iCloud auth."""

from __future__ import annotations

import hmac
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from flask import Flask, jsonify, render_template, request

from . import __version__
from .auth import AuthenticationError, ICloudAuth
from .config import AppConfig
from .database import LocationDatabase
from .web_admin import WebAdminStore


def create_app(
    database: LocationDatabase,
    auth: ICloudAuth | None = None,
    poller=None,
    admin_store: WebAdminStore | None = None,
    config: AppConfig | None = None,
) -> Flask:
    """Create and configure the Flask application."""
    package_root = Path(__file__).resolve().parent
    asset_root = package_root if (package_root / "templates").is_dir() else package_root.parents[1]
    app = Flask(
        __name__,
        template_folder=str(asset_root / "templates"),
        static_folder=str(asset_root / "static"),
    )

    runtime_config = config or AppConfig.from_env()
    web_auth_enabled = not runtime_config.web_auth_disabled
    admin_password = runtime_config.web_admin_password
    admin_store = admin_store or WebAdminStore()
    lifetime_days = runtime_config.auth_session_lifetime_days
    auth_timeout = runtime_config.web_auth_flow_timeout_seconds
    state = {"started_at": 0.0, "waiting_for_code": False, "pending_admin": None}
    state_lock = RLock()

    def require_admin() -> tuple[dict, int] | None:
        if not web_auth_enabled:
            return {"error": "Web authentication is disabled"}, 404
        supplied = request.headers.get("X-Admin-Password", "")
        valid = (
            hmac.compare_digest(supplied, admin_password)
            if admin_password
            else admin_store.verify(supplied)
        )
        if not valid:
            return {"error": "Administrator authentication failed"}, 401
        return None

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https://*.tile.openstreetmap.org; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        cache_policy = (
            "public, max-age=3600, stale-while-revalidate=86400"
            if request.endpoint == "static"
            else "no-store"
        )
        response.headers["Cache-Control"] = cache_policy
        return response

    @app.route("/")
    def index():
        """Main map view with an optional injected authentication widget."""
        html = render_template("index.html", app_version=__version__)
        if auth:
            assets = (
                '<link rel="stylesheet" href="/static/auth.css">\n'
                '<script defer src="/static/auth.js"></script>\n'
            )
            html = html.replace("</head>", f"{assets}</head>")
        return html

    @app.route("/api/auth/status")
    def api_auth_status():
        if not auth:
            return jsonify({"configured": False, "state": "unavailable"})
        status = auth.authentication_metadata(lifetime_days)
        status.update(
            web_auth_enabled=web_auth_enabled,
            admin_password_configured=bool(admin_password) or admin_store.configured,
            setup_required=not admin_password and not admin_store.configured,
            username_masked=_mask_username(auth.username),
            lifetime_days=lifetime_days,
        )
        with state_lock:
            if state["waiting_for_code"] and time.monotonic() - state["started_at"] <= auth_timeout:
                status["flow_state"] = "waiting_for_code"
            else:
                state["waiting_for_code"] = False
                status["flow_state"] = "idle"
        return jsonify(status)

    @app.route("/api/auth/start", methods=["POST"])
    def api_auth_start():
        setup_required = not admin_password and not admin_store.configured
        if not setup_required:
            denied = require_admin()
            if denied:
                return jsonify(denied[0]), denied[1]
        elif not web_auth_enabled:
            return jsonify({"error": "Web authentication is disabled"}), 404
        if not auth:
            return jsonify({"error": "Apple ID is not configured"}), 503
        payload = request.get_json(silent=True) or {}
        pending_admin = None
        if setup_required:
            try:
                pending_admin = admin_store.prepare(str(payload.get("admin_password", "")))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        password = payload.get("password") or auth.password
        if not password:
            return jsonify(
                {"error": "Enter the Apple ID password or configure ICLOUD_PASSWORD"}
            ), 400
        try:
            result = auth.begin_web_authentication(password)
            with state_lock:
                state["started_at"] = time.monotonic()
                state["waiting_for_code"] = bool(result["requires_2fa"])
                state["pending_admin"] = pending_admin
            if pending_admin and not result["requires_2fa"]:
                admin_store.save(pending_admin)
                with state_lock:
                    state["pending_admin"] = None
            return jsonify(result)
        except AuthenticationError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/auth/verify", methods=["POST"])
    def api_auth_verify():
        payload = request.get_json(silent=True) or {}
        code = str(payload.get("code", "")).strip()
        with state_lock:
            if (
                not state["waiting_for_code"]
                or time.monotonic() - state["started_at"] > auth_timeout
            ):
                state["waiting_for_code"] = False
                state["pending_admin"] = None
                return jsonify({"error": "The authentication request expired. Start again."}), 409
            pending_admin = state["pending_admin"]
        if pending_admin:
            supplied = request.headers.get("X-Admin-Password", "")
            if not admin_store.verify(supplied, pending_admin):
                return jsonify({"error": "Administrator authentication failed"}), 401
        else:
            denied = require_admin()
            if denied:
                return jsonify(denied[0]), denied[1]
        try:
            auth.complete_web_2fa(code)
            auth.get_devices()
            with state_lock:
                state["waiting_for_code"] = False
                state["pending_admin"] = None
            if pending_admin:
                admin_store.save(pending_admin)
            if poller:
                poller.wake()
            return jsonify({"status": "authenticated"})
        except AuthenticationError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/devices")
    def api_devices():
        return jsonify(database.get_devices())

    @app.route("/api/locations")
    def api_locations():
        device_id = request.args.get("device_id")
        hours = request.args.get("hours", type=int)
        start = request.args.get("start")
        end = request.args.get("end")
        limit = request.args.get("limit", type=int, default=1000)
        if limit is None or limit < 1 or limit > 5000:
            return jsonify({"error": "limit must be between 1 and 5000"}), 400
        if hours is not None and hours < 1:
            return jsonify({"error": "hours must be greater than zero"}), 400
        start_time = datetime.now() - timedelta(hours=hours) if hours else None
        try:
            if start and not hours:
                start_time = datetime.fromisoformat(start)
            end_time = datetime.fromisoformat(end) if end else None
        except ValueError:
            return jsonify({"error": "start and end must be ISO 8601 date-time values"}), 400
        if start_time and end_time and start_time > end_time:
            return jsonify({"error": "start must not be later than end"}), 400
        return jsonify(
            database.get_locations(
                device_id=device_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
        )

    @app.route("/api/locations/latest")
    def api_latest_locations():
        latest = []
        for device in database.get_devices():
            location = database.get_latest_location(device["id"])
            if location:
                location["device_name"] = device["name"]
                location["device_display_name"] = device["device_display_name"]
                latest.append(location)
        return jsonify(latest)

    @app.route("/api/stats")
    def api_stats():
        devices = database.get_devices()
        return jsonify(
            {
                "total_devices": len(devices),
                "total_locations": database.get_location_count(),
                "devices": [
                    {
                        "id": device["id"],
                        "name": device["name"],
                        "location_count": database.get_location_count(device["id"]),
                        "last_seen": device["last_seen"],
                        "latest_location": database.get_latest_location(device["id"]),
                    }
                    for device in devices
                ],
            }
        )

    @app.route("/api/system/status")
    def api_system_status():
        """Expose operational state without returning location coordinates."""
        return jsonify(
            {
                "version": __version__,
                "database_ready": database.is_ready(),
                "poller": poller.status() if poller else {"state": "not_running"},
                "configuration": runtime_config.public_web_settings(),
            }
        )

    @app.route("/health/live")
    def health_live():
        return jsonify({"status": "ok"})

    @app.route("/health/ready")
    def health_ready():
        ready = database.is_ready()
        return jsonify({"status": "ready" if ready else "not_ready"}), 200 if ready else 503

    return app


def _mask_username(username: str) -> str:
    if "@" not in username:
        return "***"
    local, domain = username.split("@", 1)
    visible = local[:1]
    return f"{visible}{'*' * max(3, len(local) - 1)}@{domain}"
