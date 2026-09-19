"""Durable append-only audit events."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260919_0003"
down_revision = "20260829_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_id", sa.String(32)),
    )
    op.create_index("ix_audit_events_created_id", "audit_events", ["created_at", "id"])
    op.execute("""CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$""")
    op.execute("""CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE OR TRUNCATE
        ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation()""")


def downgrade() -> None:
    # Explicit migration downgrade is destructive; not part of normal app operations.
    op.drop_table("audit_events")
    op.execute("DROP FUNCTION reject_audit_mutation()")
