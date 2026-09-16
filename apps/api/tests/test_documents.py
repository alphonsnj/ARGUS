from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.v1.documents import validate_file_signature
from app.services.extraction import DocumentExtractor


def test_accepts_a_valid_pdf_signature(tmp_path: Path) -> None:
    document = tmp_path / "evidence.pdf"
    document.write_bytes(b"%PDF-1.7\n")
    validate_file_signature(document, "application/pdf")


def test_rejects_a_spoofed_pdf_signature(tmp_path: Path) -> None:
    document = tmp_path / "spoofed.pdf"
    document.write_bytes(b"not-a-pdf")
    with pytest.raises(HTTPException, match="Invalid file signature"):
        validate_file_signature(document, "application/pdf")


def test_extracts_searchable_contact_metadata() -> None:
    # The metadata routine is format-independent.
    result = DocumentExtractor()._metadata(
        "Contact jane@example.com at +1 (415) 555-0123 on January 10, 2026. "
        "Acme Corporation is located at 101 Market Street."
    )
    assert result.metadata["emails"] == ["jane@example.com"]
    assert ("phone", "+1 (415) 555-0123") in result.entities
    assert ("organization", "Acme Corporation") in result.entities


def test_extracts_email_before_sentence_punctuation() -> None:
    result = DocumentExtractor()._metadata("Contact jane@example.com.")
    assert result.metadata["emails"] == ["jane@example.com"]
