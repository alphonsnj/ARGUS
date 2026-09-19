from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.deps import DbSession, SuperAdministrator
from app.models.audit import AuditEvent
from app.repositories.audit import record_event

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    action: str
    actor_id: UUID | None
    subject_id: UUID | None
    request_id: str | None


@router.get("", response_model=list[AuditResponse])
def list_audit_events(
    session: DbSession, _: SuperAdministrator,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
) -> list[AuditResponse]:
    events = session.scalars(select(AuditEvent).order_by(
        AuditEvent.created_at.desc(), AuditEvent.id.desc()
    ).limit(limit).offset(offset))
    result = [AuditResponse.model_validate(event) for event in events]
    record_event(session, "audit.listed")
    session.commit()
    return result
