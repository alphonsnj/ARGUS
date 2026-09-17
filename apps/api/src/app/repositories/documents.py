from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Document, DocumentEntity, DocumentStatus


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        owner_id: UUID,
        original_filename: str,
        content_type: str,
        byte_size: int,
        sha256: str,
        quarantine_key: str,
    ) -> Document:
        document = Document(
            owner_id=owner_id,
            original_filename=original_filename,
            content_type=content_type,
            byte_size=byte_size,
            sha256=sha256,
            quarantine_key=quarantine_key,
        )
        self._session.add(document)
        self._session.commit()
        self._session.refresh(document)
        return document

    def get_for_owner(self, document_id: UUID, owner_id: UUID) -> Document | None:
        return self._session.scalar(
            select(Document).where(Document.id == document_id, Document.owner_id == owner_id)
        )

    def get(self, document_id: UUID) -> Document | None:
        return self._session.get(Document, document_id)

    def list_for_owner(
        self, owner_id: UUID, query: str | None = None, *, limit: int = 50, offset: int = 0
    ) -> list[Document]:
        statement = select(Document).where(Document.owner_id == owner_id)
        if query:
            statement = statement.where(
                Document.search_vector.op("@@")(func.websearch_to_tsquery("english", query))
            )
        return list(self._session.scalars(
            statement.order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit).offset(offset)
        ))

    def mark_processing(self, document: Document) -> None:
        document.status = DocumentStatus.PROCESSING
        document.failure_reason = None
        self._session.commit()

    def mark_rejected(self, document: Document, reason: str) -> None:
        document.status = DocumentStatus.REJECTED
        document.failure_reason = reason[:255]
        self._session.commit()

    def mark_failed(self, document: Document, reason: str) -> None:
        self._session.rollback()
        document.status = DocumentStatus.FAILED
        document.failure_reason = reason[:255]
        self._session.commit()

    def mark_ready(
        self,
        document: Document,
        *,
        storage_key: str,
        text: str,
        metadata: dict[str, object],
        entities: list[tuple[str, str]],
    ) -> None:
        document.storage_key = storage_key
        document.quarantine_key = None
        document.extracted_text = text
        document.extracted_metadata = metadata
        document.status = DocumentStatus.READY
        document.failure_reason = None
        document.entities = [
            DocumentEntity(kind=kind, value=value, normalized_value=value.casefold())
            for kind, value in entities
        ]
        self._session.flush()
        self._session.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(search_vector=func.to_tsvector("english", text))
        )
        self._session.commit()

    def requeue(self, document: Document) -> None:
        document.status = DocumentStatus.QUEUED
        document.failure_reason = None
        self._session.commit()
