from __future__ import annotations

import io
import zipfile

import pytest

from saige_api.files.validation import (
    UploadRejectedError,
    sanitize_filename,
    validate_upload,
)

MAX = 10 * 1024 * 1024
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n"


def ooxml(marker: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(f"{marker}document.xml", "<doc/>")
    return buffer.getvalue()


def check(name: str, data: bytes) -> str:
    return validate_upload(name, io.BytesIO(data), len(data), max_bytes=MAX).mime_type


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [
        ("Resume.pdf", PDF, "application/pdf"),
        ("Passport.JPG", b"\xff\xd8\xff\xe0" + b"\x00" * 32, "image/jpeg"),
        ("shot.png", PNG, "image/png"),
        ("notes.md", b"# JMeter notes\nSelenium", "text/markdown"),
        ("data.csv", b"month,net\n2026-08,100000\n", "text/csv"),
        (
            "cv.docx",
            ooxml("word/"),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "sheet.xlsx",
            ooxml("xl/"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("legacy.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32, "application/msword"),
    ],
)
def test_accepts_genuine_files(name: str, data: bytes, mime: str) -> None:
    assert check(name, data) == mime


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("invoice.pdf", b"MZ\x90\x00 windows executable", "content_mismatch"),
        ("photo.png", PDF, "content_mismatch"),
        ("notes.txt", PNG, "content_mismatch"),
        ("fake.docx", ooxml("xl/"), "content_mismatch"),
        ("script.exe", b"MZ\x90\x00", "unsupported_type"),
        ("page.html", b"<html><script>alert(1)</script>", "unsupported_type"),
        ("image.svg", b"<svg onload=alert(1)>", "unsupported_type"),
        ("noext", PDF, "unsupported_type"),
        ("latin1.txt", "caf\xe9".encode("latin-1"), "unsupported_encoding"),
        ("empty.pdf", b"", "empty_file"),
    ],
)
def test_rejects_mismatched_or_dangerous_files(name: str, data: bytes, code: str) -> None:
    with pytest.raises(UploadRejectedError) as excinfo:
        check(name, data)
    assert excinfo.value.code == code


def test_rejects_oversized_files() -> None:
    with pytest.raises(UploadRejectedError) as excinfo:
        validate_upload("big.pdf", io.BytesIO(PDF), MAX + 1, max_bytes=MAX)
    assert excinfo.value.code == "file_too_large"


def test_rejects_zip_bombs() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("zeros.bin", b"\x00" * (20 * 1024 * 1024))  # compresses ~1000:1
    with pytest.raises(UploadRejectedError) as excinfo:
        check("bomb.zip", buffer.getvalue())
    assert excinfo.value.code == "archive_suspicious"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Resume.pdf", "Resume.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\Payslip.pdf", "Payslip.pdf"),
        ('in<va>lid:na"me?.pdf', "in_va_lid_na_me_.pdf"),
        ("tab\there.txt", "tab_here.txt"),
        ("CON.txt", "_CON.txt"),
        ("", "untitled"),
        ("...", "untitled"),
        ("e\u0301cole.pdf", "\u00e9cole.pdf"),
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_truncates_but_keeps_extension() -> None:
    name = sanitize_filename("a" * 400 + ".pdf")
    assert len(name) == 255
    assert name.endswith(".pdf")
