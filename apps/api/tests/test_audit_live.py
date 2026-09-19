import os
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.repositories.audit import record_event

pytestmark = pytest.mark.skipif(
    os.environ.get("ARGUS_LIVE_TEST") != "1", reason="Requires migrated PostgreSQL"
)


def test_audit_participates_in_transaction_and_is_append_only() -> None:
    marker = uuid4()
    with SessionLocal() as session:
        record_event(session, "document.listed", marker)
        session.flush()
        session.rollback()
        assert session.scalar(select(AuditEvent).where(AuditEvent.subject_id == marker)) is None
        record_event(session, "document.listed", marker)
        session.commit()
        event = session.scalar(select(AuditEvent).where(AuditEvent.subject_id == marker))
        assert event is not None
        # This synthetic event is deliberately retained: audit rows cannot be deleted.
        for sql in [
            "UPDATE audit_events SET action = 'changed' WHERE subject_id = :id",
            "DELETE FROM audit_events WHERE subject_id = :id",
            "TRUNCATE audit_events",
        ]:
            with pytest.raises(DBAPIError, match="append-only"), session.begin_nested():
                session.execute(text(sql), {"id": marker})
        session.rollback()
