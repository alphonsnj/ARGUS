from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.repositories.audit import record_event


def test_audit_records_only_identifiers_and_event_name() -> None:
    session = MagicMock(spec=Session)
    actor = uuid4()
    subject = uuid4()
    session.info = {"actor_id": actor, "request_id": "a" * 32, "password": "never-store"}
    record_event(session, "document.read", subject)
    event = session.add.call_args.args[0]
    assert event.actor_id == actor and event.subject_id == subject
    assert event.request_id == "a" * 32
    assert set(event.__table__.columns.keys()) == {
        "id", "created_at", "action", "actor_id", "subject_id", "request_id"
    }
    session.commit.assert_not_called()
