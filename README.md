# Find My Timeline

Track historical location data from your Apple devices using the Find My service.

Apple's Find My only shows current device locations. This tool polls your devices at random intervals and stores the history in a local database, letting you view location timelines on a map.

## Setup

```bash
pip install -e .
cp .env.example .env
# Edit .env with your Apple ID
```

## Usage

```bash
# First-time: authenticate (handles 2FA)
find-my-timeline auth

# Start polling + web UI
find-my-timeline start

# Open http://127.0.0.1:5000 in your browser
```

## Commands

| Command | Description |
|---------|-------------|
| `auth` | Authenticate with iCloud (interactive 2FA) |
| `poll` | Start location polling only |
| `web` | Start web interface only |
| `start` | Start both poller and web UI |
| `stats` | Show database statistics |
| `devices` | List tracked devices |

## Configuration

Set in `.env` or pass as CLI options:

- `ICLOUD_USERNAME` - Your Apple ID
- `ICLOUD_PASSWORD` - Password (optional, will prompt)
- `POLL_MIN_INTERVAL` - Minimum poll interval in minutes (default: 7)
- `POLL_MAX_INTERVAL` - Maximum poll interval in minutes (default: 10)
- `DATABASE_PATH` - SQLite database path (default: ./data/locations.db)
- `WEB_HOST` / `WEB_PORT` - Web server binding (default: 127.0.0.1:5000)
