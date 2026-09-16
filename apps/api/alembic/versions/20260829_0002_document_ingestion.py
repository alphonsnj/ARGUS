"""add document ingestion and search indexing

Revision ID: 20260829_0002
Revises: 20260809_0001
Create Date: 2026-08-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260829_0002"
down_revision = "20260809_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    document_status = postgresql.ENUM(
        "queued", "processing", "ready", "rejected", "failed", name="document_status", create_type=False
    )
    document_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("quarantine_key", sa.String(length=512)),
        sa.Column("storage_key", sa.String(length=512)),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("extracted_metadata", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("failure_reason", sa.String(length=255)),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_documents_owner_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index("ix_documents_owner_created", "documents", ["owner_id", "created_at"])
    op.create_index("ix_documents_search_vector", "documents", ["search_vector"], postgresql_using="gin")
    op.create_table(
        "document_entities",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("value", sa.String(length=512), nullable=False),
        sa.Column("normalized_value", sa.String(length=512), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name=op.f("fk_document_entities_document_id_documents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_entities")),
    )
    op.create_index("ix_document_entities_kind_value", "document_entities", ["kind", "normalized_value"])


def downgrade() -> None:
    op.drop_index("ix_document_entities_kind_value", table_name="document_entities")
    op.drop_table("document_entities")
    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.drop_index("ix_documents_owner_created", table_name="documents")
    op.drop_table("documents")
    postgresql.ENUM(name="document_status").drop(op.get_bind(), checkfirst=True)
