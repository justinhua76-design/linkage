"""Orchestrates validation -> deterministic engine -> provenance record."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app import __version__
from app.domain import phenoage as engine
from app.domain.validation import (
    Issue,
    LodPolicy,
    RawMeasurement,
    Severity,
    ValidationReport,
    validate_inputs,
)

PHENOAGE_PLAUSIBLE_LOW = 0.0
PHENOAGE_PLAUSIBLE_HIGH = 120.0


@dataclass
class ComputationOutcome:
    report: ValidationReport
    output: engine.PhenoAgeOutput | None = None
    computed_at: datetime | None = None
    extra_errors: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.output is not None


def model_info() -> dict[str, str]:
    return {
        "model_id": engine.MODEL_ID,
        "model_version": engine.MODEL_VERSION,
        "engine_version": __version__,
        "coefficients_sha256": engine.coefficients_fingerprint(),
        "algorithm_source": engine.ALGORITHM_SOURCE,
    }


def run_phenoage(
    measurements: dict[str, RawMeasurement | None],
    age: float | None,
    *,
    lod_policy: LodPolicy,
    max_lab_span_days: int,
) -> ComputationOutcome:
    report = validate_inputs(measurements, age, lod_policy=lod_policy, max_lab_span_days=max_lab_span_days)
    outcome = ComputationOutcome(report=report)
    if not report.ok or report.canonical is None:
        return outcome
    try:
        outcome.output = engine.compute_phenoage(report.canonical)
    except engine.PhenoAgeComputationError:
        outcome.extra_errors.append(Issue("COMPUTATION_FAILED", "phenoage", "数值计算失败，未生成年龄结果"))
        return outcome
    if not (PHENOAGE_PLAUSIBLE_LOW <= outcome.output.phenoage <= PHENOAGE_PLAUSIBLE_HIGH):
        report.issues.append(
            Issue(
                "PHENOAGE_EXTRAPOLATED",
                "phenoage",
                "PhenoAge 超出 [0, 120] 岁，属于模型外推区域，数值不宜解读",
                Severity.WARNING,
            )
        )
    outcome.computed_at = datetime.now(UTC)
    return outcome
