import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    REJECTED = "rejected"
    FAILED = "failed"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_owner_created", "owner_id", "created_at"),
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda statuses: [item.value for item in statuses],
        ),
        default=DocumentStatus.QUEUED,
        nullable=False,
    )
    quarantine_key: Mapped[str | None] = mapped_column(String(512))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extracted_metadata: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    search_vector: Mapped[object | None] = mapped_column(TSVECTOR)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    entities: Mapped[list["DocumentEntity"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="selectin"
    )


class DocumentEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_entities"
    __table_args__ = (Index("ix_document_entities_kind_value", "kind", "normalized_value"),)

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(512), nullable=False)
    document: Mapped[Document] = relationship(back_populates="entities")
