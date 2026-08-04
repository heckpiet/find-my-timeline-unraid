# Unraid validation record

## Release candidate

- Application version: `0.2.0`
- Validation date: 2026-07-27
- Unraid OS: 7.3.2
- Container image: `ghcr.io/heckpiet/find-my-timeline-unraid:latest`
- Network mode: bridge
- WebUI container port: 5000

## Persistent paths

| Purpose | Container path | Unraid host path |
|---|---|---|
| SQLite database | `/app/data` | `/mnt/user/appdata/find-my-timeline/data` |
| Apple session and cookies | `/root/.find-my-timeline` | `/mnt/user/appdata/find-my-timeline/session` |

## Tests completed

| Test | Result |
|---|---|
| Pull public image from GHCR without credentials | Passed |
| Create container through the Unraid template | Passed |
| Start without privileged mode | Passed |
| Reach the WebUI through the configured host port | Passed |
| Authenticate with Apple ID and a newly requested 2FA code | Passed |
| Discover devices available through Apple Find My | Passed |
| Poll and store device location records | Passed |
| Display devices and historical data in the WebUI | Passed |
| Restart container without losing SQLite data | Passed |
| Recreate container without losing Apple session data | Passed |
| Docker health check reaches `healthy` | Passed |
| Mask administrator and optional Apple password fields | Passed |

## Security observations

- The WebUI contains sensitive location history and was tested only on a trusted private network.
- Port 5000 must not be forwarded directly to the public internet.
- Remote access should use a VPN or an authenticated HTTPS reverse proxy.
- The Apple session directory and database directory must be included in protected backups.
- Screenshots, logs and issue reports must redact Apple IDs, verification codes, device identifiers and location data.

## Regression checks for future releases

Future releases should repeat the tests above and additionally verify any new environment variables, database migrations, authentication behavior and rollback instructions.

## Version 0.2.1 release-candidate checks

The following checks are required before tagging 0.2.1 and must not be marked as passed solely by GitHub-hosted CI:

- start with an expired or unavailable Apple session and confirm the poller enters `waiting_for_authentication` without exiting
- complete WebUI 2FA and confirm a poll starts without restarting the container
- temporarily interrupt outbound connectivity and confirm polling recovers afterward
- verify `/health/live` remains healthy while Apple authentication is required
- verify `/health/ready` reflects SQLite availability
- confirm `/api/system/status` contains no coordinates, passwords, codes or reusable session material
- run the manually approved `Unraid validation` workflow against the exact public 0.2.1 image

The automated Unraid smoke workflow uses an empty temporary data directory and does not validate Apple authentication or production persistence. Those remain manual release checks using protected backups and the release-candidate image.

## Version 0.2.2 release-candidate checks

- update an existing container that still contains `WEB_AUTH_ENABLED=false` and confirm the setup button remains available
- leave `WEB_ADMIN_PASSWORD` empty and complete **Set up & re-authenticate**
- verify the chosen administrator password is never present in plaintext in appdata or logs
- restart and recreate the container, then confirm the persisted administrator password still works
- set `WEB_AUTH_DISABLED=true` and confirm browser authentication becomes unavailable
- confirm successful first-run Apple 2FA wakes the poller without another restart

## Version 0.3.0 release-candidate checks

- upgrade an existing 0.2.2 container while preserving both appdata mappings
- confirm the settings view reports version 0.3.0 and the configured non-secret runtime values
- verify invalid ports, intervals and timeouts fail fast with a clear configuration error
- confirm repeated observations for the same device and timestamp are not inserted twice
- verify ordinary logs contain neither precise coordinates nor authentication secrets
- exercise map, timeline, device filter, recovery banner and settings on desktop and mobile widths
- install the built wheel outside the source tree and confirm templates and static assets render
- confirm the public image is available for both `linux/amd64` and `linux/arm64`
- run the manually approved isolated Unraid validation against the exact public 0.3.0 image

## Version 0.4.0 release-candidate checks

- remove `ICLOUD_USERNAME` from a fresh container and confirm the WebUI and health check start normally
- complete Apple ID, Apple password and 2FA setup entirely through the WebUI
- confirm `apple-identity.json` contains the Apple ID but no Apple password or verification code
- recreate and update the container while retaining the session mapping and confirm the Apple ID remains available
- verify a password shorter than 12 characters is rejected unless both risk confirmations are supplied
- verify a strong administrator password does not show or require the weak-password warning
- confirm successful onboarding changes the poller from `waiting_for_setup` to active polling
