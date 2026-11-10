"""Role-based access control (Sprint 1: static bearer tokens from env)."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings


class Role(StrEnum):
    ADMIN = "admin"
    CLINICIAN = "clinician"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


class Permission(StrEnum):
    PATIENT_CREATE = "patient:create"
    PATIENT_READ = "patient:read"
    LAB_WRITE = "lab:write"
    LAB_READ = "lab:read"
    BIOAGE_COMPUTE = "bioage:compute"
    BIOAGE_READ = "bioage:read"
    AUDIT_READ = "audit:read"
    BHRT_DRAFT = "bhrt:draft"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.CLINICIAN: frozenset(
        {
            Permission.PATIENT_CREATE,
            Permission.PATIENT_READ,
            Permission.LAB_WRITE,
            Permission.LAB_READ,
            Permission.BIOAGE_COMPUTE,
            Permission.BIOAGE_READ,
            Permission.BHRT_DRAFT,
        }
    ),
    Role.RESEARCHER: frozenset(
        {
            Permission.PATIENT_READ,
            Permission.LAB_READ,
            Permission.BIOAGE_COMPUTE,
            Permission.BIOAGE_READ,
        }
    ),
    Role.VIEWER: frozenset({Permission.PATIENT_READ, Permission.LAB_READ, Permission.BIOAGE_READ}),
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role

    def can(self, perm: Permission) -> bool:
        return perm in ROLE_PERMISSIONS[self.role]


_bearer = HTTPBearer(auto_error=False)


def get_principal(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "缺少或无效的访问令牌"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = creds.credentials.encode()
    match: Principal | None = None
    for entry in settings.token_table:
        # constant-time compare against every entry
        if hmac.compare_digest(presented, entry["token"].encode()):
            match = Principal(user_id=entry["user_id"], role=Role(entry["role"]))
    if match is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "缺少或无效的访问令牌"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.principal = match
    return match


def require(perm: Permission):  # noqa: ANN201
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(perm):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"角色 {principal.role} 无权限 {perm}"},
            )
        return principal

    return dep
