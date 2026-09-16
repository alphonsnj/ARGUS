from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.extraction import DocumentExtractor


def test_mixed_pdf_preserves_text_and_ocrs_only_scanned_pages() -> None:
    pages = [MagicMock(), MagicMock(), MagicMock()]
    for page, text in zip(pages, ["First page", "", "Third page"], strict=True):
        page.extract_text.return_value = text
    extractor = DocumentExtractor()
    source = Path("mixed.pdf")
    with patch("app.services.extraction.PdfReader") as reader:
        reader.return_value.pages = pages
        with patch.object(extractor, "_ocr_scanned_pdf", return_value="Scanned page") as ocr:
            assert extractor._extract_pdf(source) == "First page\nScanned page\nThird page"
            ocr.assert_called_once_with(source, 2)
