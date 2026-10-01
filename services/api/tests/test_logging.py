from __future__ import annotations

from saige_api.core.logging import REDACTED, redact_mapping


def test_sensitive_keys_are_redacted() -> None:
    event = {
        "event": "oauth_refresh",
        "access_token": "ya29.abc",
        "refresh_token": "1//xyz",
        "password": "hunter2",
        "client_secret": "s3cr3t",
        "document_content": "Net salary: 1,00,000",
        "ocr_text": "Passport No. X1234567",
        "user_id": "8b7e...",
    }
    redacted = redact_mapping(event)
    for key in (
        "access_token",
        "refresh_token",
        "password",
        "client_secret",
        "document_content",
        "ocr_text",
    ):
        assert redacted[key] == REDACTED
    assert redacted["user_id"] == "8b7e..."
    assert redacted["event"] == "oauth_refresh"


def test_bearer_tokens_scrubbed_from_values() -> None:
    redacted = redact_mapping({"note": "upstream said Bearer abc.def.ghi was invalid"})
    assert "abc.def.ghi" not in redacted["note"]


def test_nested_structures_are_redacted() -> None:
    redacted = redact_mapping({"request": {"headers": {"authorization": "Basic Zm9v"}}})
    assert redacted["request"]["headers"]["authorization"] == REDACTED
