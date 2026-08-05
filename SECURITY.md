# Security and privacy reporting

Find My Timeline processes Apple authentication material and precise location history. Do not include production databases, session files, Apple IDs, device identifiers, verification codes, passwords or real location screenshots in a public issue or pull request.

## Reporting a vulnerability or privacy exposure

Use GitHub's private vulnerability reporting feature on the repository Security page. Include a minimal reproduction with synthetic data. If a public artifact accidentally contains personal data, identify the affected path or commit without repeating the exposed value.

## Repository privacy controls

- CI rejects non-synthetic email addresses in tracked text files.
- PNG textual and EXIF metadata is rejected.
- Pull requests require an explicit privacy checklist.
- Documentation screenshots must use synthetic demonstration data.

Automated checks cannot reliably recognize personal data rendered as image pixels. Every screenshot therefore requires human review before commit.
