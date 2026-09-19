from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent

Action = Literal[
    "document.created", "document.processing", "document.ready", "document.failed",
    "document.rejected", "document.retried", "document.read", "document.listed",
    "document.searched", "session.created", "session.revoked", "sessions.revoked",
    "authentication.failed", "audit.listed",
]


def record_event(
    session: Session, action: Action, subject_id: UUID | None = None,
    *, actor_id: UUID | None = None,
) -> None:
    """Append inside the caller's transaction; never store credentials or evidence text."""
    session.add(AuditEvent(
        action=action, subject_id=subject_id,
        actor_id=actor_id if actor_id is not None else session.info.get("actor_id"),
        request_id=session.info.get("request_id"),
    ))
