from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import IssueOut, Number

DISCLAIMER = (
    "仅供研究和内部验证使用 (Research use only)。PhenoAge 为基于 Levine 2018 公式的确定性计算结果，"
    "不构成疾病诊断或治疗建议。"
)


class BiomarkerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Number | None = Field(default=None, description="Measured value in `unit`")
    unit: str | None = Field(default=None, max_length=32)
    below_lod: bool = Field(default=False, description="Result reported below limit of detection")
    lod: Number | None = Field(default=None, description="Limit of detection, same unit as value")
    collected_on: date | None = None


class PhenoAgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chronological_age: Number | None = Field(description="Age in years at sample collection")
    biomarkers: dict[str, BiomarkerInput] | None = Field(default=None, description="Nine biomarkers keyed by code")
    patient_id: uuid.UUID | None = Field(default=None, description="If set, the result is persisted for this patient")
    lab_result_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Compute from stored lab results (requires patient_id); mutually exclusive with `biomarkers`",
    )


class ModelInfo(BaseModel):
    model_id: str
    model_version: str
    engine_version: str
    coefficients_sha256: str
    algorithm_source: str


class MeasurementOut(BaseModel):
    code: str
    original_value: float | None
    original_unit: str | None
    normalised_unit: str | None
    canonical_value: float | None
    canonical_unit: str
    conversion_factor: float | None
    quality_status: str
    reference_low: float
    reference_high: float
    below_lod: bool
    lod_canonical: float | None
    imputation: str | None
    collected_on: date | None


class PhenoAgeResponse(BaseModel):
    status: str = "ok"
    result_id: uuid.UUID | None
    patient_id: uuid.UUID | None
    phenoage: float
    phenoage_rounded: float
    chronological_age: float
    phenoage_minus_chronological_age: float
    mortality_score: float
    linear_predictor: float
    lod_policy: str
    computed_at: datetime
    model: ModelInfo
    inputs: list[MeasurementOut]
    lab_result_ids: list[uuid.UUID] = []
    warnings: list[IssueOut]
    disclaimer: str = DISCLAIMER


class PhenoAgeRejected(BaseModel):
    status: str = "rejected"
    code: str = "VALIDATION_FAILED"
    message: str
    errors: list[IssueOut]
    warnings: list[IssueOut]
    inputs: list[MeasurementOut]


class BiomarkerMeta(BaseModel):
    code: str
    name_en: str
    name_zh: str
    canonical_unit: str
    allowed_units: list[str]
    plausible_low: float
    plausible_high: float
    reference_low: float
    reference_high: float
    supports_lod: bool
    notes: str


class BiomarkerCatalog(BaseModel):
    model: ModelInfo
    biomarkers: list[BiomarkerMeta]
    age_hard_range: tuple[float, float]
    age_training_range: tuple[float, float]
    lod_policy: str
