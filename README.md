# Find My Timeline for Unraid

Unofficial Unraid-ready fork of [kennym/find-my-timeline](https://github.com/kennym/find-my-timeline).

Find My Timeline polls devices available through Apple's Find My service at configurable intervals and stores their historical positions in a local SQLite database. The WebUI displays devices, routes and timelines on an interactive map.

> This project is not affiliated with or endorsed by Apple or Lime Technology.

![Preview](preview.png)
![Preview Detail](preview2.png)
![Preview Timeline](preview3.png)

## Unraid installation

Install the app from Community Applications once published, or use the template directly:

```text
https://raw.githubusercontent.com/heckpiet/find-my-timeline-unraid/master/templates/find-my-timeline.xml
```

Docker image:

```text
ghcr.io/heckpiet/find-my-timeline-unraid:latest
```

## Apple authentication

The WebUI now shows an estimated session lifetime and can optionally start a new Apple authentication flow.

The countdown is based on the last successful authentication and defaults to 90 days. It is only an estimate. Apple can invalidate a session earlier, so a successful location poll remains the authoritative signal.

### Recommended WebUI flow

1. Set `ICLOUD_USERNAME`.
2. Enable `WEB_AUTH_ENABLED`.
3. Set a long, unique `WEB_ADMIN_PASSWORD`.
4. Open the WebUI and select **Re-authenticate**.
5. Enter the WebUI administrator password and Apple ID password.
6. Enter the new verification code shown on a trusted Apple device.

The Apple ID password and verification code are not written to SQLite or the authentication metadata file. Session cookies remain stored in `/root/.find-my-timeline`.

### CLI fallback

```bash
find-my-timeline auth
```

For Docker:

```bash
docker exec -it find-my-timeline find-my-timeline auth
docker restart find-my-timeline
```

Legacy Apple two-step authentication remains CLI-only.

## Configuration

| Variable | Default | Description |
|---|---:|---|
| `ICLOUD_USERNAME` | — | Apple ID email address |
| `ICLOUD_PASSWORD` | unset | Optional persistent password; leaving it unset is safer |
| `POLL_MIN_INTERVAL` | `7` | Minimum interval between requests in minutes |
| `POLL_MAX_INTERVAL` | `10` | Maximum interval between requests in minutes |
| `DATABASE_PATH` | `/app/data/locations.db` | SQLite database path |
| `WEB_HOST` | `0.0.0.0` | Web server binding inside the container |
| `WEB_PORT` | `5000` | Internal WebUI port |
| `WEB_AUTH_ENABLED` | `false` | Enables browser-based Apple re-authentication |
| `WEB_ADMIN_PASSWORD` | unset | Protects the browser authentication endpoints |
| `AUTH_SESSION_LIFETIME_DAYS` | `90` | Estimated Apple session lifetime used by the countdown |
| `WEB_AUTH_FLOW_TIMEOUT_SECONDS` | `600` | Maximum time allowed between starting auth and entering 2FA |
| `TZ` | `Europe/Berlin` | Container timezone in the Unraid template |

## Persistent data

| Container path | Purpose |
|---|---|
| `/app/data` | SQLite database containing device and location history |
| `/root/.find-my-timeline` | Apple session, cookies and non-secret auth timestamp metadata |

Back up both paths. Location data and Apple session cookies are sensitive.

## Security notice

The location map itself does not include a built-in user login. `WEB_ADMIN_PASSWORD` protects only the endpoints that start and complete Apple authentication. It does not protect map or location-history access.

Do not expose port 5000 directly to the internet. Use one or more of the following:

- trusted local network access
- WireGuard or Tailscale
- HTTPS through a reverse proxy
- reverse-proxy authentication such as Authelia, Authentik or OAuth2 Proxy

Use a unique administrator password with at least 20 random characters. Do not reuse the Apple ID password. Avoid configuring `ICLOUD_PASSWORD` unless unattended recovery is more important than reducing stored secrets.

The application adds `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` and `Cache-Control` response headers. Browser authentication requests expire after the configured timeout and require the administrator password on every write request.

## Docker usage outside Unraid

```bash
mkdir -p data session

docker run -d \
  --name find-my-timeline \
  --restart unless-stopped \
  -p 5000:5000 \
  -e ICLOUD_USERNAME=your-apple-id@example.com \
  -e WEB_AUTH_ENABLED=true \
  -e WEB_ADMIN_PASSWORD='replace-with-a-long-random-password' \
  -e POLL_MIN_INTERVAL=7 \
  -e POLL_MAX_INTERVAL=10 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/session:/root/.find-my-timeline" \
  ghcr.io/heckpiet/find-my-timeline-unraid:latest
```

## Commands

| Command | Description |
|---|---|
| `find-my-timeline auth` | Authenticate with iCloud and handle 2FA |
| `find-my-timeline poll` | Start location polling only |
| `find-my-timeline web` | Start the WebUI only |
| `find-my-timeline start` | Start polling and the WebUI |
| `find-my-timeline stats` | Show database statistics |
| `find-my-timeline devices` | List tracked devices |

## Community Applications publishing checklist

1. Merge the prepared feature branch into `master`.
2. Confirm the Docker build workflow succeeds.
3. Set `ghcr.io/heckpiet/find-my-timeline-unraid` visibility to **Public**.
4. Pull and test the image on Unraid.
5. Confirm both appdata paths survive container updates.
6. Test first authentication, re-authentication, an invalid admin password and an expired 2FA flow.
7. Validate and scan the repository at the Unraid Community Applications submission portal.
8. Submit the repository for review.

## License and attribution

The application remains licensed under the MIT License. Original copyright notices and attribution are retained in `LICENSE`.
