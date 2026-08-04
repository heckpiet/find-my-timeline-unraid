# Release process

This repository uses `pyproject.toml` as the single source of truth for the application version. Semantic-version image tags are immutable and are published only from a matching Git tag.

## Continuous integration

Every pull request and push to `master` runs:

1. Ruff linting and formatting plus pytest on Python 3.10, 3.11 and 3.12 with at least 70% coverage.
2. Source and wheel builds followed by a clean installed-wheel WebUI smoke test.
3. XML parsing for the Unraid template.
4. A Docker build followed by readiness and rendered-WebUI smoke tests.
5. CodeQL analysis for Python and browser JavaScript. Dependabot separately proposes grouped weekly updates.

These jobs never publish an image and require only read access to repository contents.

## Preparing a new version

1. Create a release branch from `master`, for example `release-0.4.2`.
2. Update the version in `pyproject.toml`.
3. Add a dated section to `CHANGELOG.md`.
4. Update `<Changes>` and `<Date>` in `templates/find-my-timeline.xml`.
5. Add the stable image tag as a `<Branch>` entry in the Unraid template.
6. Update documentation for new variables, paths, security behavior or migrations.
7. Open a pull request and require all CI checks to pass.
8. Merge the pull request into `master`.
9. Create and push the exact matching tag, for example:

   ```bash
   git switch master
   git pull --ff-only
   git tag -s v0.4.2 -m "Find My Timeline v0.4.2"
   git push origin v0.4.2
   ```

The release workflow rejects a tag that does not match `pyproject.toml`. A valid tag publishes multi-architecture `linux/amd64` and `linux/arm64` images, SBOM and provenance metadata, then creates the GitHub release. It publishes `latest`, `X.Y.Z`, `vX.Y.Z` and `X.Y`. Existing `X.Y.Z` and `vX.Y.Z` tags must never be rebuilt from an ordinary branch push.

## Isolated Unraid smoke test

The optional `Unraid validation` workflow runs only through `workflow_dispatch` on a self-hosted runner labeled `unraid`. It pulls an explicitly selected public image, mounts a temporary empty data directory, binds only to `127.0.0.1:15010`, verifies readiness and removes the test container and data afterward. It never mounts production appdata or Apple session files.

Because this is a public repository, do not enable self-hosted runners for `pull_request` events. Configure the `unraid-validation` GitHub environment with required reviewer approval and use a dedicated, minimally privileged or ephemeral runner rather than the production Unraid host where possible.

## Validation before Community Applications submission

Test the exact public image and template that users will receive:

```bash
docker pull ghcr.io/heckpiet/find-my-timeline-unraid:VERSION
```

Verify at least:

- container starts without privileged mode
- WebUI is reachable through the configured host port
- `/health/live` and `/health/ready` succeed
- Apple authentication and 2FA work
- a fresh container starts without Apple credentials and completes onboarding through the WebUI
- the persisted Apple ID survives container replacement without storing the Apple password
- authentication recovery resumes polling without a container restart
- device polling records new locations
- database and Apple session data survive container replacement
- masked template values remain masked
- no secrets or coordinates appear in ordinary logs
- rollback to the previous image works with a protected database backup
- the raw template, icon, README and screenshots are publicly reachable

Then run `Validate` and `Scan` in the Unraid Community Applications submission portal.

## Rollback

Unraid users can select a previous immutable image tag instead of `latest`, for example `ghcr.io/heckpiet/find-my-timeline-unraid:0.2.2`.

Persistent data is stored outside the image. Before rollback, back up `/app/data` and `/root/.find-my-timeline`. Database changes must remain backward-compatible or include explicit migration and rollback notes in `CHANGELOG.md`.

## Package visibility

The GHCR package must remain public so Community Applications and Unraid hosts can pull it without GitHub credentials.
