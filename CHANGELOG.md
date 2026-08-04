# Changelog

All notable changes to this Unraid-focused fork are documented in this file.

The project follows Semantic Versioning. Release images are published from matching Git tags with `latest`, the plain version such as `0.2.1`, the prefixed version such as `v0.2.1`, and a major/minor tag such as `0.2`.

## [Unreleased]

## [0.4.2] - 2026-08-04

### Changed

- Clarify which saved Apple ID is used during setup and re-authentication.
- Separate the Apple ID email address from the password for that Apple Account.
- Add accessible Show/Hide controls to all password fields in the authentication dialog.
- Improve field guidance, focus handling and desktop dialog spacing.
- Version static asset URLs so Unraid updates cannot leave an older WebUI in the browser cache.

## [0.4.1] - 2026-08-04

### Added

- Add a CI privacy scan that rejects non-synthetic email addresses in tracked text files.
- Reject PNG text/EXIF metadata and JPEG EXIF metadata from repository images.
- Add a pull-request privacy checklist covering Apple IDs, device identifiers and real locations.
- Add private vulnerability and privacy-incident reporting guidance.

### Changed

- Make synthetic screenshot and fixture requirements explicit in contributor documentation.

## [0.4.0] - 2026-08-04

### Added

- Add complete first-run Apple ID, Apple password and 2FA onboarding to the WebUI.
- Persist only the Apple ID address in the protected session volume after successful authentication.
- Allow a deliberately weak WebUI administrator password only after two explicit security confirmations.
- Add a poller `waiting_for_setup` state so a fresh container remains healthy before onboarding.

### Changed

- Make `ICLOUD_USERNAME` optional and remove it from the recommended Docker and Unraid setup.
- Start the full application and WebUI without any Apple credentials in the container configuration.
- Keep Apple passwords and verification codes exclusively in the short-lived authentication flow.

### Security

- Enforce both weak-password acknowledgements on the server, independently of browser validation.
- Write the persisted Apple ID atomically with restrictive file permissions.

## [0.3.0] - 2026-08-03

### Added

- Add a dedicated responsive settings view for application health, polling configuration, health endpoints, privacy guidance and Apple authentication.
- Show the running application version in the sidebar and system status API.
- Add validated, typed runtime configuration with clear startup errors for invalid values.
- Add package and rendered-WebUI smoke tests, CodeQL analysis and grouped Dependabot updates.
- Add active device-filter context, recovery guidance, a skip link and improved live status feedback.

### Changed

- Move Apple re-authentication from the crowded device sidebar into the settings view.
- Improve navigation, timeline buttons, form controls and keyboard focus styling.
- Refresh the README and screenshots with synthetic demonstration data.
- Normalize stored timestamps to UTC, enable SQLite WAL and busy-timeout handling, and avoid duplicate location inserts.
- Stop logging precise coordinates during normal polling and use structured exception logging.
- Build the runtime container from an installed wheel in a smaller multi-stage image.
- Pin supported dependency ranges and raise the enforced test coverage threshold to 70 percent.
- Add strict browser security headers, Subresource Integrity for Leaflet and explicit static-asset caching.

### Fixed

- Include WebUI templates and static assets in built Python wheels so the installed package can render the dashboard outside an editable checkout.
- Make configuration validation, authentication metadata writes and polling recovery more robust.

## [0.2.2] - 2026-08-03

### Fixed

- Prevent the legacy `WEB_AUTH_ENABLED=false` value on existing Unraid containers from disabling the re-authentication button.
- Replace the disabled button with a guided first-run administrator setup.

### Added

- Persist the first-run WebUI administrator password as a salted PBKDF2-SHA256 hash in the existing session volume.
- Require successful Apple authentication and verification before committing the first-run administrator credential.
- Add regression coverage for legacy Unraid configuration migration, password hashing and setup validation.

### Changed

- Browser re-authentication is available by default and can be explicitly disabled with `WEB_AUTH_DISABLED=true`.
- `WEB_ADMIN_PASSWORD` remains supported for environment-managed installations but is no longer required.

## [0.2.1] - 2026-08-03

### Fixed

- Keep the poller alive after Apple authentication and network failures instead of stopping permanently.
- Wake the poller immediately after successful WebUI re-authentication.
- Reject invalid date ranges and unbounded location limits with HTTP 400 responses.
- Prevent device names and model descriptions from visually running together in the desktop sidebar.
- Escape authentication and timeline values before inserting them into the page.

### Added

- Poller state, last successful poll, next attempt and safe error status through `/api/system/status`.
- Separate `/health/live` and `/health/ready` endpoints.
- Regression tests for authentication recovery, health endpoints and API validation.
- Pull-request CI for Python, the Unraid template and a real container smoke test.
- Tag-only multi-architecture releases with SBOM and provenance metadata.
- Optional manually approved smoke testing on an isolated Unraid self-hosted runner.

### Changed

- Serve the WebUI with Waitress instead of Flask's development server.
- Publish immutable semantic-version images only from matching Git tags.

## [0.2.0] - 2026-07-27

### Added

- Unraid Community Applications template with persistent database and Apple session paths.
- Public Docker image publishing through GitHub Container Registry.
- Responsive WebUI 2.0 with desktop and mobile navigation.
- Device cards, route map, exact date and time filtering, status metrics and chronological timeline.
- Apple session status and estimated re-authentication countdown.
- Optional protected browser-based Apple 2FA re-authentication.
- Configurable administrator password for authentication actions.
- Docker health check and OCI image metadata.
- Versioned Docker image tags derived from `pyproject.toml`.
- Automated GitHub release creation for new versions merged into `master`.
- Community Applications screenshots and selectable stable image tags.

### Fixed

- Apple 2FA now explicitly requests a fresh verification code before validating it.
- CLI version output now comes from installed package metadata and no longer needs a separate hard-coded version update.

### Security

- Apple ID passwords and verification codes used by the WebUI authentication flow are not written to SQLite or authentication metadata.
- Sensitive password fields are masked in the Unraid template.
- Security response headers and expiring in-memory authentication flows are documented and enabled.
- The documentation clearly warns against exposing location history directly to the internet.

### Validation

The release candidate was tested successfully on Unraid OS 7.3.2 with:

- public GHCR image pull
- installation through the Unraid Docker template
- persistent SQLite database storage
- persistent Apple session and cookie storage
- Apple two-factor authentication
- device discovery and location polling
- WebUI access on port 5000
- container restart and data persistence
- Docker health check

## [0.1.0] - 2026-07-24

### Added

- Initial fork of `kennym/find-my-timeline`.
- Basic Docker packaging, SQLite location history, polling service and map-based WebUI.

[0.2.0]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.2.0
[0.2.1]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.2.1
[0.2.2]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.2.2
[0.3.0]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.3.0
[0.4.0]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.4.0
[0.4.1]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.4.1
[0.4.2]: https://github.com/heckpiet/find-my-timeline-unraid/releases/tag/v0.4.2
[0.1.0]: https://github.com/heckpiet/find-my-timeline-unraid/commits/master
