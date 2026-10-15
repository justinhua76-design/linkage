"""Application settings, loaded exclusively from environment variables / .env.

Secrets (DB password, API tokens) must never be committed; see .env.example.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.validation import DEFAULT_LOD_POLICY, DEFAULT_MAX_LAB_SPAN_DAYS, LodPolicy

VALID_ROLES = {"admin", "clinician", "researcher", "viewer"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", description="development|test|production")
    database_url: str = "postgresql+psycopg://bioage:bioage@localhost:5432/bioage"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # JSON list: [{"token": "...", "user_id": "...", "role": "clinician"}]
    # Sprint-1 static bearer tokens; to be replaced by OIDC (see docs/PRODUCT_SPEC.md).
    auth_tokens: str = "[]"

    crp_lod_policy: LodPolicy = DEFAULT_LOD_POLICY
    max_lab_span_days: int = DEFAULT_MAX_LAB_SPAN_DAYS

    @field_validator("auth_tokens")
    @classmethod
    def _validate_tokens(cls, v: str) -> str:
        data = json.loads(v)
        if not isinstance(data, list):
            raise ValueError("AUTH_TOKENS must be a JSON list")
        for entry in data:
            if not {"token", "user_id", "role"} <= set(entry):
                raise ValueError("AUTH_TOKENS entries need token, user_id, role")
            if entry["role"] not in VALID_ROLES:
                raise ValueError(f"invalid role {entry['role']!r}")
            if len(entry["token"]) < 16:
                raise ValueError("AUTH_TOKENS token must be at least 16 characters")
        return v

    @property
    def token_table(self) -> list[dict[str, str]]:
        return json.loads(self.auth_tokens)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
