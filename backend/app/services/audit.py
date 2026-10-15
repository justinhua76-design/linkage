"""Audit trail. Records actor/action/resource only - never clinical values."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import Principal
from app.db.models import AuditLog

_FORBIDDEN_DETAIL_KEYS = {"value", "values", "inputs", "age", "birth_date", "pseudonym", "notes"}


def record(
    db: Session,
    principal: Principal,
    action: str,
    resource_type: str,
    resource_id: str | None,
    outcome: str = "success",
    request_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    details = dict(details or {})
    leaked = _FORBIDDEN_DETAIL_KEYS & set(details)
    if leaked:
        raise ValueError(f"audit details must not contain clinical fields: {sorted(leaked)}")
    entry = AuditLog(
        actor=principal.user_id,
        role=principal.role.value,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_id=request_id,
        details=details,
    )
    db.add(entry)
    return entry
