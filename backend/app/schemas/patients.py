from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Number

Sex = Literal["female", "male", "other", "unknown"]
LabSource = Literal["manual_entry", "lab_import", "synthetic"]


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pseudonym: str = Field(
        pattern=r"^[A-Za-z0-9_-]{3,64}$",
        description="Pseudonymous study code. Do NOT use real names or national IDs.",
    )
    sex: Sex
    birth_date: date | None = None
    is_synthetic: bool = False


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pseudonym: str
    sex: str
    birth_date: date | None
    is_synthetic: bool
    created_at: datetime
    created_by: str


class LabMeasurementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    biomarker: str
    value: Number | None = None
    unit: str = Field(max_length=32)
    below_lod: bool = False
    lod: Number | None = None
    reference_low: Number | None = None
    reference_high: Number | None = None
    reference_unit: str | None = Field(default=None, max_length=32)


class LabBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collected_on: date
    source: LabSource = "manual_entry"
    source_detail: str | None = Field(default=None, max_length=255)
    measurements: list[LabMeasurementIn] = Field(min_length=1, max_length=50)


class LabResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    biomarker: str
    value_original: float | None
    unit_original: str
    value_canonical: float | None
    unit_canonical: str
    conversion_factor: float | None
    below_lod: bool
    lod_original: float | None
    collected_on: date
    source: str
    source_detail: str | None
    reference_low: float | None
    reference_high: float | None
    reference_unit: str | None
    reference_source: str
    quality_status: str
    quality_issues: list
    created_at: datetime
    created_by: str


class BioAgeResultSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID | None
    model_id: str
    model_version: str
    chronological_age: float
    phenoage: float
    mortality_score: float
    computed_at: datetime
    computed_by: str


class PatientOverview(BaseModel):
    patient: PatientOut
    latest_labs: dict[str, LabResultOut]
    labs: list[LabResultOut]
    results: list[BioAgeResultSummary]
