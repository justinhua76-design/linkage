"""Persistence model.

* ``patients`` - pseudonymised subjects (no names / national ids in Sprint 1).
* ``lab_results`` - one row per biomarker measurement, storing the original
  value+unit exactly as entered, the canonical value, collection date, source,
  reference range, LOD information and a data-quality status.
* ``bioage_results`` - immutable computation records with full provenance.
* ``audit_logs`` - who did what, when, on which resource (no clinical values).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType


def _now() -> datetime:
    return datetime.now(UTC)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pseudonym: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sex: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    labs: Mapped[list[LabResult]] = relationship(back_populates="patient")
    results: Mapped[list[BioAgeResult]] = relationship(back_populates="patient")

    __table_args__ = (CheckConstraint("sex in ('female','male','other','unknown')", name="ck_patient_sex"),)


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    biomarker: Mapped[str] = mapped_column(String(32), nullable=False)
    value_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_original: Mapped[str] = mapped_column(String(32), nullable=False)
    value_canonical: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_canonical: Mapped[str] = mapped_column(String(32), nullable=False)
    conversion_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    below_lod: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lod_original: Mapped[float | None] = mapped_column(Float, nullable=True)
    collected_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_source: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False)
    quality_issues: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="labs")

    __table_args__ = (
        Index("ix_lab_results_patient_biomarker_date", "patient_id", "biomarker", "collected_on"),
        CheckConstraint("source in ('manual_entry','lab_import','synthetic')", name="ck_lab_source"),
    )


class BioAgeResult(Base):
    __tablename__ = "bioage_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    coefficients_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_source: Mapped[str] = mapped_column(Text, nullable=False)
    chronological_age: Mapped[float] = mapped_column(Float, nullable=False)
    phenoage: Mapped[float] = mapped_column(Float, nullable=False)
    mortality_score: Mapped[float] = mapped_column(Float, nullable=False)
    linear_predictor: Mapped[float] = mapped_column(Float, nullable=False)
    lod_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    inputs: Mapped[dict] = mapped_column(JsonType, nullable=False)
    lab_result_ids: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_by: Mapped[str] = mapped_column(String(64), nullable=False)

    patient: Mapped[Patient | None] = relationship(back_populates="results")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Structured, non-clinical metadata only (e.g. error codes, counts).
    details: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)

    __table_args__ = (Index("ix_audit_logs_occurred_at", "occurred_at"),)
