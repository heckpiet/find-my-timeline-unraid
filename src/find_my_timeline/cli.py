"""Command-line interface for Find My Timeline."""

import logging
import sys
from importlib.metadata import PackageNotFoundError, version
from threading import Thread

import click
from dotenv import load_dotenv
from waitress import serve

from .auth import AuthenticationError, ICloudAuth
from .config import AppConfig, ConfigurationError
from .database import LocationDatabase
from .poller import LocationPoller
from .web import create_app

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

try:
    APP_VERSION = version("find-my-timeline")
except PackageNotFoundError:
    APP_VERSION = "development"


def get_config() -> AppConfig:
    """Get configuration from environment variables."""
    try:
        return AppConfig.from_env()
    except ConfigurationError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group()
@click.version_option(version=APP_VERSION)
def main():
    """Find My Timeline - Track your Apple device locations over time."""


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password", hide_input=True)
def auth(username, password):
    """Authenticate with iCloud and store the session."""
    config = get_config()
    username = username or config.username or click.prompt("Enter your Apple ID")
    password = password or config.password or click.prompt("Enter your password", hide_input=True)
    click.echo(f"Authenticating as {username}...")
    try:
        handler = ICloudAuth(username, password)
        handler.authenticate()
        click.echo("Authentication successful. Session and metadata saved.")
        devices = handler.get_devices()
        click.echo(f"Found {len(devices)} device(s):")
        for device in devices:
            location_status = "Has location" if device.get("location") else "No location"
            click.echo(
                f"  - {device['name']} ({device['device_display_name']}) - {location_status}"
            )
    except AuthenticationError as exc:
        click.echo(f"Authentication failed: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password", hide_input=True)
@click.option("--min-interval", type=int, help="Minimum polling interval in minutes")
@click.option("--max-interval", type=int, help="Maximum polling interval in minutes")
def poll(username, password, min_interval, max_interval):
    """Start the location polling service."""
    config = get_config()
    username = username or config.username
    password = password or config.password
    min_interval = min_interval if min_interval is not None else config.min_interval
    max_interval = max_interval if max_interval is not None else config.max_interval
    if not username:
        click.echo("Error: ICLOUD_USERNAME is required", err=True)
        sys.exit(1)
    handler = ICloudAuth(username, password)
    database = LocationDatabase(config.db_path)
    poller = LocationPoller(
        handler,
        database,
        min_interval,
        max_interval,
        auth_retry_interval=config.auth_retry_interval,
    )
    poller.on_poll(
        lambda locations: (
            click.echo(f"Recorded {len(locations)} location(s)") if locations else None
        )
    )
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
    database = LocationDatabase(config.db_path)
    handler = ICloudAuth(config.username, config.password) if config.username else None
    app = create_app(database, handler, config=config)
    host = host or config.web_host
    port = port if port is not None else config.web_port
    click.echo(f"Starting web server at http://{host}:{port}")
    serve(app, host=host, port=port, threads=4)


@main.command()
@click.option("--username", "-u", help="iCloud username (Apple ID)")
@click.option("--password", "-p", help="iCloud password", hide_input=True)
@click.option("--host", help="Web server host")
@click.option("--port", type=int, help="Web server port")
def start(username, password, host, port):
    """Start both the poller and web interface."""
    config = get_config()
    username = username or config.username
    password = password or config.password
    host = host or config.web_host
    port = port if port is not None else config.web_port
    if not username:
        click.echo("Error: ICLOUD_USERNAME is required", err=True)
        sys.exit(1)

    handler = ICloudAuth(username, password)
    database = LocationDatabase(config.db_path)
    poller = LocationPoller(
        auth=handler,
        database=database,
        min_interval=config.min_interval,
        max_interval=config.max_interval,
        auth_retry_interval=config.auth_retry_interval,
    )
    app = create_app(database, handler, poller, config=config)

    click.echo("Starting Find My Timeline")
    click.echo(f"  Polling interval: {config.min_interval}-{config.max_interval} minutes")
    click.echo(f"  Web interface: http://{host}:{port}")
    click.echo(f"  Database: {config.db_path}")

    Thread(target=poller.start, daemon=True).start()
    try:
        serve(app, host=host, port=port, threads=4)
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
    finally:
        poller.stop()


@main.command()
def stats():
    """Show database statistics."""
    config = get_config()
    db_path = config.db_path
    if not db_path.exists():
        click.echo("No database found. Run 'poll' first.")
        return
    database = LocationDatabase(db_path)
    devices = database.get_devices()
    click.echo(f"Database: {db_path}")
    click.echo(f"Total locations: {database.get_location_count():,}")
    click.echo(f"Devices: {len(devices)}")
    for device in devices:
        latest = database.get_latest_location(device["id"])
        click.echo(f"\n  {device['name']} ({device['device_display_name']})")
        click.echo(f"    Locations: {database.get_location_count(device['id']):,}")
        click.echo(f"    Last seen: {latest['timestamp'] if latest else 'Never'}")


@main.command()
def devices():
    """List all tracked devices."""
    config = get_config()
    db_path = config.db_path
    if not db_path.exists():
        click.echo("No database found. Run 'poll' first.")
        return
    database = LocationDatabase(db_path)
    for device in database.get_devices():
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
