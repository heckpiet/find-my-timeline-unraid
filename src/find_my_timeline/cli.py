"""Command-line interface for Find My Timeline."""

import logging
import os
import sys
from pathlib import Path
from threading import Thread

import click
from dotenv import load_dotenv

from .auth import ICloudAuth, AuthenticationError
from .database import LocationDatabase
from .poller import LocationPoller
from .web import create_app

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_config():
    """Get configuration from environment variables."""
    return {
        "username": os.getenv("ICLOUD_USERNAME"),
        "password": os.getenv("ICLOUD_PASSWORD"),
        "min_interval": int(os.getenv("POLL_MIN_INTERVAL", "7")),
        "max_interval": int(os.getenv("POLL_MAX_INTERVAL", "10")),
        "db_path": os.getenv("DATABASE_PATH", "./data/locations.db"),
        "web_host": os.getenv("WEB_HOST", "127.0.0.1"),
        "web_port": int(os.getenv("WEB_PORT", "5000")),
    }


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Find My Timeline - Track your Apple device locations over time."""
    pass


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password", hide_input=True)
def auth(username, password):
    """Authenticate with iCloud and store session."""
    config = get_config()
    username = username or config["username"]

    if not username:
        username = click.prompt("Enter your Apple ID")

    password = password or config["password"]
    if not password:
        password = click.prompt("Enter your password", hide_input=True)

    click.echo(f"Authenticating as {username}...")

    try:
        auth_handler = ICloudAuth(username, password)
        auth_handler.authenticate()
        click.echo("Authentication successful! Session saved.")

        # Show devices
        devices = auth_handler.get_devices()
        click.echo(f"\nFound {len(devices)} device(s):")
        for device in devices:
            location_status = "Has location" if device.get("location") else "No location"
            click.echo(f"  - {device['name']} ({device['device_display_name']}) - {location_status}")

    except AuthenticationError as e:
        click.echo(f"Authentication failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password")
@click.option("--min-interval", type=int, help="Minimum polling interval in minutes")
@click.option("--max-interval", type=int, help="Maximum polling interval in minutes")
def poll(username, password, min_interval, max_interval):
    """Start the location polling service."""
    config = get_config()

    username = username or config["username"]
    password = password or config["password"]
    min_interval = min_interval or config["min_interval"]
    max_interval = max_interval or config["max_interval"]

    if not username:
        click.echo("Error: iCloud username required. Set ICLOUD_USERNAME or use --username", err=True)
        sys.exit(1)

    click.echo(f"Starting poller (interval: {min_interval}-{max_interval} minutes)")
    click.echo(f"Database: {config['db_path']}")

    auth_handler = ICloudAuth(username, password)
    database = LocationDatabase(config["db_path"])
    poller = LocationPoller(
        auth=auth_handler,
        database=database,
        min_interval=min_interval,
        max_interval=max_interval,
    )

    # Add callback to log recorded locations
    def on_poll(locations):
        if locations:
            click.echo(f"Recorded {len(locations)} location(s)")

    poller.on_poll(on_poll)

    try:
        poller.start()
    except KeyboardInterrupt:
        click.echo("\nStopping poller...")


@main.command()
@click.option("--host", "-h", help="Host to bind to")
@click.option("--port", "-p", type=int, help="Port to bind to")
def web(host, port):
    """Start the web interface."""
    config = get_config()

    host = host or config["web_host"]
    port = port or config["web_port"]

    database = LocationDatabase(config["db_path"])
    app = create_app(database)

    click.echo(f"Starting web server at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password")
@click.option("--host", help="Web server host")
@click.option("--port", type=int, help="Web server port")
def start(username, password, host, port):
    """Start both the poller and web interface."""
    config = get_config()

    username = username or config["username"]
    password = password or config["password"]
    host = host or config["web_host"]
    port = port or config["web_port"]

    if not username:
        click.echo("Error: iCloud username required. Set ICLOUD_USERNAME or use --username", err=True)
        sys.exit(1)

    auth_handler = ICloudAuth(username, password)
    database = LocationDatabase(config["db_path"])

    # Create poller
    poller = LocationPoller(
        auth=auth_handler,
        database=database,
        min_interval=config["min_interval"],
        max_interval=config["max_interval"],
    )

    # Create web app
    app = create_app(database)

    click.echo(f"Starting Find My Timeline")
    click.echo(f"  Polling interval: {config['min_interval']}-{config['max_interval']} minutes")
    click.echo(f"  Web interface: http://{host}:{port}")
    click.echo(f"  Database: {config['db_path']}")

    # Start poller in background thread
    poller_thread = Thread(target=poller.start, daemon=True)
    poller_thread.start()

    # Start web server in main thread
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
        poller.stop()


@main.command()
def stats():
    """Show database statistics."""
    config = get_config()
    db_path = Path(config["db_path"])

    if not db_path.exists():
        click.echo("No database found. Run 'poll' first to start collecting data.")
        return

    database = LocationDatabase(db_path)
    devices = database.get_devices()
    total = database.get_location_count()

    click.echo(f"Database: {db_path}")
    click.echo(f"Total locations: {total:,}")
    click.echo(f"Devices: {len(devices)}")

    for device in devices:
        count = database.get_location_count(device["id"])
        latest = database.get_latest_location(device["id"])
        latest_time = latest["timestamp"] if latest else "Never"

        click.echo(f"\n  {device['name']} ({device['device_display_name']})")
        click.echo(f"    Locations: {count:,}")
        click.echo(f"    Last seen: {latest_time}")


@main.command()
def devices():
    """List all tracked devices."""
    config = get_config()
    db_path = Path(config["db_path"])

    if not db_path.exists():
        click.echo("No database found. Run 'poll' first to start collecting data.")
        return

    database = LocationDatabase(db_path)
    device_list = database.get_devices()

    if not device_list:
        click.echo("No devices found.")
        return

    click.echo(f"Tracked devices ({len(device_list)}):\n")

    for device in device_list:
        latest = database.get_latest_location(device["id"])
        click.echo(f"  {device['name']}")
        click.echo(f"    Type: {device['device_display_name']}")
        click.echo(f"    ID: {device['id']}")
        if latest:
            click.echo(f"    Last location: ({latest['latitude']:.6f}, {latest['longitude']:.6f})")
            click.echo(f"    Last seen: {latest['timestamp']}")
        click.echo()


if __name__ == "__main__":
    main()
