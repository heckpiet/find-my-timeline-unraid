"""Fail when tracked files contain non-synthetic email addresses or image metadata."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

EMAIL_PATTERN = re.compile(rb"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
ALLOWED_DOMAINS = {
    b"example.com",
    b"example.invalid",
    b"example.org",
    b"users.noreply.github.com",
}
TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
PNG_METADATA_CHUNKS = {b"eXIf", b"iTXt", b"tEXt", b"zTXt"}


def tracked_paths(repository: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return [repository / item.decode() for item in result.stdout.split(b"\0") if item]


def scan_email_addresses(path: Path, data: bytes) -> list[str]:
    findings = []
    for line_number, line in enumerate(data.splitlines(), start=1):
        for match in EMAIL_PATTERN.finditer(line):
            if match.group(1).lower() not in ALLOWED_DOMAINS:
                findings.append(f"{path}:{line_number}: non-synthetic email address [redacted]")
    return findings


def scan_png_metadata(path: Path, data: bytes) -> list[str]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return [f"{path}: invalid PNG signature"]
    findings = []
    offset = 8
    while offset + 12 <= len(data):
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            return [f"{path}: malformed PNG chunk"]
        if chunk_type in PNG_METADATA_CHUNKS:
            findings.append(f"{path}: embedded {chunk_type.decode()} metadata is not allowed")
        offset = chunk_end
        if chunk_type == b"IEND":
            break
    return findings


def scan_jpeg_metadata(path: Path, data: bytes) -> list[str]:
    if not data.startswith(b"\xff\xd8"):
        return [f"{path}: invalid JPEG signature"]
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            break
        marker = data[offset + 1]
        if marker in {0xDA, 0xD9}:
            break
        length = int.from_bytes(data[offset + 2 : offset + 4], "big")
        if length < 2 or offset + 2 + length > len(data):
            return [f"{path}: malformed JPEG segment"]
        if marker in {0xE1, 0xED, 0xFE}:
            return [f"{path}: embedded EXIF, XMP, IPTC or comment metadata is not allowed"]
        offset += 2 + length
    return []


def scan_paths(paths: list[Path], repository: Path) -> list[str]:
    findings = []
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        relative = path.relative_to(repository)
        if path.suffix.lower() in TEXT_SUFFIXES or path.name.startswith(".env"):
            findings.extend(scan_email_addresses(relative, data))
        elif path.suffix.lower() == ".png":
            findings.extend(scan_png_metadata(relative, data))
        elif path.suffix.lower() in {".jpg", ".jpeg"}:
            findings.extend(scan_jpeg_metadata(relative, data))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repository = args.repository.resolve()
    findings = scan_paths(tracked_paths(repository), repository)
    if findings:
        print("Privacy scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("Privacy scan passed: no non-synthetic email addresses or image metadata found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
