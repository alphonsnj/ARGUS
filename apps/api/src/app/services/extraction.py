import re
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from docx import Document as WordDocument
from PIL import Image
from pypdf import PdfReader

EMAIL_PATTERN = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w+-])")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
ADDRESS_PATTERN = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,5}\s"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b",
    re.IGNORECASE,
)
ORGANIZATION_PATTERN = re.compile(
    r"\b[A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,4}\s"
    r"(?:Inc\.?|LLC|Ltd\.?|Limited|Corp\.?|Corporation|University|Hospital|Foundation|Agency)\b"
)


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    metadata: dict[str, object]
    entities: list[tuple[str, str]]


def normalized_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join(value.split()).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


class DocumentExtractor:
    def extract(self, path: Path, content_type: str) -> ExtractionResult:
        if content_type == "application/pdf":
            text = self._extract_pdf(path)
        elif (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            text = self._extract_docx(path)
        elif content_type.startswith("image/"):
            text = self._extract_image(path)
        else:
            raise ExtractionError("Unsupported document content type")
        compact_text = " ".join(text.replace("\x00", " ").split())
        if not compact_text:
            raise ExtractionError("No readable text was extracted from the document")
        return self._metadata(compact_text)

    def _extract_pdf(self, path: Path) -> str:
        try:
            reader = PdfReader(str(path))
            if len(reader.pages) > 100:
                raise ExtractionError("PDF exceeds the 100-page processing limit")
            pages = [page.extract_text() or "" for page in reader.pages]
            # OCR each image-only page, even in otherwise searchable PDFs.
            return "\n".join(
                text if text.strip() else self._ocr_scanned_pdf(path, index + 1)
                for index, text in enumerate(pages)
            )
        except ExtractionError:
            raise
        except Exception as error:
            raise ExtractionError("PDF text extraction failed") from error

    def _ocr_scanned_pdf(self, path: Path, page_number: int) -> str:
        try:
            with tempfile.TemporaryDirectory(prefix="argus-pdf-ocr-") as directory:
                output_prefix = Path(directory) / "page"
                subprocess.run(
                    ["pdftoppm", "-png", "-r", "200", "-f", str(page_number),
                     "-l", str(page_number), str(path), str(output_prefix)],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                pages = sorted(Path(directory).glob("page-*.png"))
                if not pages:
                    raise ExtractionError("PDF did not contain renderable pages")
                return "\n".join(self._extract_image(page) for page in pages)
        except ExtractionError:
            raise
        except (OSError, subprocess.SubprocessError) as error:
            raise ExtractionError("PDF OCR failed") from error

    def _extract_docx(self, path: Path) -> str:
        try:
            document = WordDocument(str(path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        except Exception as error:
            raise ExtractionError("DOCX text extraction failed") from error

    def _extract_image(self, path: Path) -> str:
        try:
            with Image.open(path) as image:
                return str(pytesseract.image_to_string(image, timeout=60))
        except Exception as error:
            raise ExtractionError("Image OCR failed") from error

    def _metadata(self, text: str) -> ExtractionResult:
        fields = {
            "emails": normalized_unique(EMAIL_PATTERN.findall(text)),
            "phones": normalized_unique(PHONE_PATTERN.findall(text)),
            "dates": normalized_unique(DATE_PATTERN.findall(text)),
            "addresses": normalized_unique(ADDRESS_PATTERN.findall(text)),
            "organizations": normalized_unique(ORGANIZATION_PATTERN.findall(text)),
        }
        entities = [
            *[("email", value) for value in fields["emails"]],
            *[("phone", value) for value in fields["phones"]],
            *[("date", value) for value in fields["dates"]],
            *[("address", value) for value in fields["addresses"]],
            *[("organization", value) for value in fields["organizations"]],
        ]
        metadata: dict[str, object] = {**fields, "character_count": len(text)}
        return ExtractionResult(text=text, metadata=metadata, entities=entities)
