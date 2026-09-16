import logging
import tempfile
from pathlib import Path
from uuid import UUID

from app.models import DocumentStatus
from app.repositories.documents import DocumentRepository
from app.services.extraction import DocumentExtractor, ExtractionError
from app.services.malware import (
    ClamAvScanner,
    MalwareDetectedError,
    MalwareScannerUnavailableError,
)
from app.services.storage import ObjectStorage

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: ObjectStorage,
        scanner: ClamAvScanner,
        extractor: DocumentExtractor,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._scanner = scanner
        self._extractor = extractor

    def process(self, document_id: UUID, *, resume: bool = False) -> None:
        document = self._repository.get(document_id)
        allowed = {DocumentStatus.QUEUED}
        if resume:
            allowed.add(DocumentStatus.PROCESSING)
        if document is None or document.status not in allowed:
            return
        self._repository.mark_processing(document)
        source_key = document.storage_key or document.quarantine_key
        if source_key is None:
            self._repository.mark_failed(document, "Document source is unavailable")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="argus-document-") as directory:
                local_path = Path(directory) / "source"
                self._storage.download_file(source_key, local_path)
                self._scanner.scan(local_path)
                result = self._extractor.extract(local_path, document.content_type)
                storage_key = document.storage_key or (
                    f"documents/{document.id}/{document.original_filename}"
                )
                if document.storage_key is None:
                    self._storage.copy(source_key, storage_key)
                self._repository.mark_ready(
                    document,
                    storage_key=storage_key,
                    text=result.text,
                    metadata=result.metadata,
                    entities=result.entities,
                )
                if source_key != storage_key:
                    try:
                        self._storage.delete(source_key)
                    except Exception:
                        logger.exception("Quarantine cleanup failed for %s", document_id)
        except MalwareDetectedError as error:
            if document.quarantine_key:
                self._storage.delete(document.quarantine_key)
            self._repository.mark_rejected(document, str(error))
        except (MalwareScannerUnavailableError, ExtractionError) as error:
            self._repository.mark_failed(document, str(error))
        except Exception:
            self._repository.mark_failed(document, "Document processing failed")
