from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Permission, Principal, require
from app.db.models import AuditLog
from app.db.session import get_db

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    occurred_at: datetime
    actor: str
    role: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    request_id: str | None
    details: dict


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Principal = Depends(require(Permission.AUDIT_READ)),
) -> list[AuditLogOut]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit))
    return [
        AuditLogOut.model_validate({**{c: getattr(r, c) for c in AuditLogOut.model_fields}, "id": str(r.id)})
        for r in rows
    ]
