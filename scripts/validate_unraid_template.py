"""Validate the Unraid Community Applications template and its local assets."""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "find-my-timeline.xml"
RAW_PREFIX = "/heckpiet/find-my-timeline-unraid/master/"


def local_asset(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "raw.githubusercontent.com":
        raise ValueError(f"Asset must use raw.githubusercontent.com over HTTPS: {url}")
    if not parsed.path.startswith(RAW_PREFIX):
        raise ValueError(f"Asset URL does not point to this repository: {url}")
    return ROOT / parsed.path.removeprefix(RAW_PREFIX)


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as image:
        signature = image.read(24)
    if len(signature) != 24 or signature[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Screenshot is not a valid PNG: {path}")
    return struct.unpack(">II", signature[16:24])


def main() -> None:
    root = ET.parse(TEMPLATE).getroot()
    if root.tag != "Container" or root.attrib.get("version") != "2":
        raise ValueError("Template must use the Unraid Container v2 format")

    required = ("Name", "Repository", "Category", "Icon", "Overview", "Project", "Support")
    for field in required:
        if not (root.findtext(field) or "").strip():
            raise ValueError(f"Missing required Community Applications field: {field}")

    template_date = date.fromisoformat((root.findtext("Date") or "").strip())
    if template_date > date.today():
        raise ValueError("Template date must not be in the future")

    icon = local_asset((root.findtext("Icon") or "").strip())
    if not icon.is_file() or icon.suffix.lower() != ".svg":
        raise ValueError(f"Missing SVG app icon: {icon}")

    screenshots = [(node.text or "").strip() for node in root.findall("Screenshot")]
    if len(screenshots) < 3:
        raise ValueError("Community Applications listing requires at least three screenshots")

    for screenshot in screenshots:
        path = local_asset(screenshot)
        if not path.is_file():
            raise ValueError(f"Missing screenshot: {path}")
        width, height = png_dimensions(path)
        if width < 1200 or height < 600:
            raise ValueError(f"Screenshot is too small ({width}x{height}): {path}")

    print(f"Validated {TEMPLATE.relative_to(ROOT)} with {len(screenshots)} screenshots")


if __name__ == "__main__":
    main()
