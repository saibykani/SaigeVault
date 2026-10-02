"""Server-side upload validation. Nothing the client says is trusted.

- File type is detected from content (magic bytes / container structure) and
  must agree with the extension, which must be on the allow-list.
- Office Open XML / ZIP archives are inspected for zip-bomb characteristics
  without extracting anything.
- Text formats must be valid UTF-8 without NUL bytes.
- Filenames are sanitised (no paths, control or reserved characters).
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from saige_api.models.enums import DocumentType

MAX_FILENAME_LENGTH = 255
ZIP_MAX_ENTRIES = 10_000
ZIP_MAX_UNCOMPRESSED = 2 * 1024**3  # 2 GiB total
ZIP_MAX_RATIO = 200  # per entry; legitimate documents rarely exceed ~20
SNIFF_BYTES = 8192

OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class UploadRejectedError(Exception):
    """`code` and `message` are safe to show to the user."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class FileKind:
    extension: str
    mime_type: str
    default_document_type: DocumentType


KINDS: dict[str, FileKind] = {
    k.extension: k
    for k in (
        FileKind("pdf", "application/pdf", DocumentType.UNCLASSIFIED),
        FileKind("doc", "application/msword", DocumentType.UNCLASSIFIED),
        FileKind(
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            DocumentType.UNCLASSIFIED,
        ),
        FileKind("xls", "application/vnd.ms-excel", DocumentType.UNCLASSIFIED),
        FileKind(
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            DocumentType.UNCLASSIFIED,
        ),
        FileKind("ppt", "application/vnd.ms-powerpoint", DocumentType.UNCLASSIFIED),
        FileKind(
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            DocumentType.UNCLASSIFIED,
        ),
        FileKind("csv", "text/csv", DocumentType.UNCLASSIFIED),
        FileKind("txt", "text/plain", DocumentType.UNCLASSIFIED),
        FileKind("md", "text/markdown", DocumentType.UNCLASSIFIED),
        FileKind("json", "application/json", DocumentType.UNCLASSIFIED),
        FileKind("xml", "application/xml", DocumentType.UNCLASSIFIED),
        FileKind("png", "image/png", DocumentType.IMAGE),
        FileKind("jpg", "image/jpeg", DocumentType.IMAGE),
        FileKind("jpeg", "image/jpeg", DocumentType.IMAGE),
        FileKind("webp", "image/webp", DocumentType.IMAGE),
        FileKind("gif", "image/gif", DocumentType.IMAGE),
        FileKind("zip", "application/zip", DocumentType.UNCLASSIFIED),
    )
}
TEXT_EXTENSIONS = frozenset({"csv", "txt", "md", "json", "xml"})
OOXML_MARKERS = {"docx": "word/", "xlsx": "xl/", "pptx": "ppt/"}

_RESERVED = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_WINDOWS_RESERVED = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)


def sanitize_filename(raw: str | None) -> str:
    """Basename only, NFC-normalised, no control/reserved characters, ≤255 chars."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = unicodedata.normalize("NFC", name)
    name = _RESERVED.sub("_", name).strip(" .")
    stem, dot, ext = name.rpartition(".")
    if stem.lower() in _WINDOWS_RESERVED or (not dot and name.lower() in _WINDOWS_RESERVED):
        name = f"_{name}"
    if not name or name.strip("_") == "":
        name = "untitled"
    if len(name) > MAX_FILENAME_LENGTH:
        stem, dot, ext = name.rpartition(".")
        keep = MAX_FILENAME_LENGTH - (len(ext) + 1 if dot and len(ext) <= 16 else 0)
        name = (
            f"{(stem or name)[:keep]}.{ext}"
            if dot and len(ext) <= 16
            else name[:MAX_FILENAME_LENGTH]
        )
    return name


def extension_of(name: str) -> str | None:
    _, dot, ext = name.rpartition(".")
    return ext.lower() if dot and ext else None


_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"PK\x03\x04", "zip"),
    (b"PK\x05\x06", "zip"),
    (OLE2, "ole2"),
)


def _sniff(head: bytes) -> str | None:
    """Coarse content family from magic bytes."""
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return next((family for magic, family in _MAGIC if head.startswith(magic)), None)


def _check_zip(stream: BinaryIO, extension: str) -> None:
    try:
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if len(infos) > ZIP_MAX_ENTRIES:
                raise UploadRejectedError(
                    "archive_too_many_entries", "The archive has too many entries."
                )
            total = 0
            for info in infos:
                total += info.file_size
                if info.compress_size and info.file_size / info.compress_size > ZIP_MAX_RATIO:
                    raise UploadRejectedError(
                        "archive_suspicious", "The archive looks like a decompression bomb."
                    )
            if total > ZIP_MAX_UNCOMPRESSED:
                raise UploadRejectedError(
                    "archive_too_large", "The archive expands to more than 2 GiB."
                )
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        raise UploadRejectedError(
            "corrupt_file", "The file is corrupt or not a valid archive."
        ) from exc
    marker = OOXML_MARKERS.get(extension)
    if marker and (
        "[Content_Types].xml" not in names or not any(n.startswith(marker) for n in names)
    ):
        raise UploadRejectedError(
            "content_mismatch", f"This file is not a valid .{extension} document."
        )


def _check_text(stream: BinaryIO, extension: str) -> None:
    decoder_input = stream.read()
    if b"\x00" in decoder_input:
        raise UploadRejectedError(
            "content_mismatch", f"This is not a valid .{extension} text file."
        )
    try:
        text = decoder_input.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadRejectedError(
            "unsupported_encoding", "Text files must be UTF-8 encoded."
        ) from exc
    if extension == "xml" and text.strip() and not text.lstrip().startswith("<"):
        raise UploadRejectedError("content_mismatch", "This is not a valid XML file.")


_EXPECTED_FAMILY = {
    "pdf": "pdf",
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "gif": "gif",
    "webp": "webp",
    "zip": "zip",
    "docx": "zip",
    "xlsx": "zip",
    "pptx": "zip",
    "doc": "ole2",
    "xls": "ole2",
    "ppt": "ole2",
}


def validate_upload(filename: str, stream: BinaryIO, size: int, *, max_bytes: int) -> FileKind:
    """Validate an upload already spooled to `stream`. Returns the detected kind.

    `stream` is left positioned at offset 0.
    """
    if size <= 0:
        raise UploadRejectedError("empty_file", "The file is empty.")
    if size > max_bytes:
        raise UploadRejectedError(
            "file_too_large", f"Files can be at most {max_bytes // (1024 * 1024)} MB."
        )
    extension = extension_of(filename)
    kind = KINDS.get(extension or "")
    if kind is None:
        raise UploadRejectedError(
            "unsupported_type",
            "This file type isn't supported. Supported: "
            + ", ".join(sorted({k.extension.upper() for k in KINDS.values()})),
        )
    stream.seek(0)
    head = stream.read(SNIFF_BYTES)
    stream.seek(0)
    try:
        if kind.extension in TEXT_EXTENSIONS:
            if _sniff(head) is not None:
                raise UploadRejectedError(
                    "content_mismatch", f"The file's content doesn't match .{kind.extension}."
                )
            _check_text(stream, kind.extension)
        else:
            family = _sniff(head)
            if family != _EXPECTED_FAMILY[kind.extension]:
                raise UploadRejectedError(
                    "content_mismatch", f"The file's content doesn't match .{kind.extension}."
                )
            if family == "zip":
                _check_zip(stream, kind.extension)
    finally:
        stream.seek(0)
    return kind


def read_head(data: bytes) -> io.BytesIO:  # pragma: no cover - test helper
    return io.BytesIO(data)
