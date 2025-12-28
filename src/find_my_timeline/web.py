"""Flask web application for viewing location history."""

from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request

from .database import LocationDatabase


def create_app(database: LocationDatabase) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder="../../templates",
        static_folder="../../static",
    )

    @app.route("/")
    def index():
        """Main map view."""
        return render_template("index.html")

    @app.route("/api/devices")
    def api_devices():
        """Get all devices."""
        devices = database.get_devices()
        return jsonify(devices)

    @app.route("/api/locations")
    def api_locations():
        """Get location history with optional filters."""
        device_id = request.args.get("device_id")
        hours = request.args.get("hours", type=int)
        start = request.args.get("start")
        end = request.args.get("end")
        limit = request.args.get("limit", type=int, default=1000)

        start_time = None
        end_time = None

        if hours:
            start_time = datetime.now() - timedelta(hours=hours)
        elif start:
            start_time = datetime.fromisoformat(start)

        if end:
            end_time = datetime.fromisoformat(end)

        locations = database.get_locations(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        return jsonify(locations)

    @app.route("/api/locations/latest")
    def api_latest_locations():
        """Get the latest location for each device."""
        devices = database.get_devices()
        latest = []

        for device in devices:
            location = database.get_latest_location(device["id"])
            if location:
                location["device_name"] = device["name"]
                location["device_display_name"] = device["device_display_name"]
                latest.append(location)

        return jsonify(latest)

    @app.route("/api/stats")
    def api_stats():
        """Get database statistics."""
        devices = database.get_devices()
        total_locations = database.get_location_count()

        device_stats = []
        for device in devices:
            count = database.get_location_count(device["id"])
            latest = database.get_latest_location(device["id"])
            device_stats.append({
                "id": device["id"],
                "name": device["name"],
                "location_count": count,
                "last_seen": device["last_seen"],
                "latest_location": latest,
            })

        return jsonify({
            "total_devices": len(devices),
            "total_locations": total_locations,
            "devices": device_stats,
        })

    return app
