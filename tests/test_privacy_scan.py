from scripts.privacy_scan import scan_email_addresses, scan_jpeg_metadata, scan_png_metadata


def test_privacy_scan_allows_synthetic_email_and_redacts_real_address(tmp_path):
    path = tmp_path / "document.md"

    assert scan_email_addresses(path, b"demo@example.com") == []
    private_address = b"private" + b"@" + b"personal.test"
    findings = scan_email_addresses(path, private_address)

    assert len(findings) == 1
    assert "private" not in findings[0]
    assert "[redacted]" in findings[0]


def test_privacy_scan_rejects_png_text_metadata(tmp_path):
    path = tmp_path / "screenshot.png"
    png = b"\x89PNG\r\n\x1a\n" + (4).to_bytes(4, "big") + b"tEXt" + b"test" + b"0000"

    assert "metadata is not allowed" in scan_png_metadata(path, png)[0]


def test_privacy_scan_rejects_jpeg_exif_after_jfif_segment(tmp_path):
    path = tmp_path / "screenshot.jpg"
    jfif = b"\xff\xe0" + (4).to_bytes(2, "big") + b"JF"
    exif = b"\xff\xe1" + (4).to_bytes(2, "big") + b"EX"

    assert "metadata is not allowed" in scan_jpeg_metadata(path, b"\xff\xd8" + jfif + exif)[0]
