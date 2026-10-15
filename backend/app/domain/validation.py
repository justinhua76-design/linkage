"""Input validation for PhenoAge: units, ranges, missing data, CRP/LOD handling.

The validator is deliberately conservative: if *any* error-severity issue is
found, no canonical input set is produced and therefore no age can be
computed. Warnings never block computation but are always returned with the
result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.domain.biomarkers import (
    AGE_HARD_HIGH,
    AGE_HARD_LOW,
    AGE_TRAINING_HIGH,
    AGE_TRAINING_LOW,
    BIOMARKERS,
    BiomarkerCode,
    BiomarkerDef,
)
from app.domain.phenoage import CanonicalInputs
from app.domain.units import UnitError, convert, normalise_unit


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class QualityStatus(StrEnum):
    VALID = "valid"
    OUT_OF_REFERENCE_RANGE = "out_of_reference_range"
    BELOW_LOD_IMPUTED = "below_lod_imputed"
    MISSING = "missing"
    UNIT_ERROR = "unit_error"
    INVALID_VALUE = "invalid_value"
    IMPLAUSIBLE = "implausible"

    @property
    def usable(self) -> bool:
        return self in {
            QualityStatus.VALID,
            QualityStatus.OUT_OF_REFERENCE_RANGE,
            QualityStatus.BELOW_LOD_IMPUTED,
        }


class LodPolicy(StrEnum):
    """How CRP results reported as below the limit of detection are handled."""

    LOD_DIV_SQRT2 = "lod_div_sqrt2"  # substitute LOD / sqrt(2) (NHANES convention)
    LOD = "lod"  # substitute the LOD itself
    REJECT = "reject"  # refuse to compute


DEFAULT_LOD_POLICY = LodPolicy.LOD_DIV_SQRT2
DEFAULT_MAX_LAB_SPAN_DAYS = 30


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str
    severity: Severity = Severity.ERROR

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass
class RawMeasurement:
    value: float | None
    unit: str | None
    below_lod: bool = False
    lod: float | None = None
    collected_on: date | None = None


@dataclass
class ValidatedMeasurement:
    code: str
    original_value: float | None
    original_unit: str | None
    normalised_unit: str | None
    canonical_value: float | None
    canonical_unit: str
    conversion_factor: float | None
    quality_status: QualityStatus
    reference_low: float
    reference_high: float
    below_lod: bool = False
    lod_canonical: float | None = None
    imputation: str | None = None
    collected_on: date | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "original_value": self.original_value,
            "original_unit": self.original_unit,
            "normalised_unit": self.normalised_unit,
            "canonical_value": self.canonical_value,
            "canonical_unit": self.canonical_unit,
            "conversion_factor": self.conversion_factor,
            "quality_status": self.quality_status.value,
            "reference_low": self.reference_low,
            "reference_high": self.reference_high,
            "below_lod": self.below_lod,
            "lod_canonical": self.lod_canonical,
            "imputation": self.imputation,
            "collected_on": self.collected_on.isoformat() if self.collected_on else None,
        }


@dataclass
class ValidationReport:
    measurements: dict[str, ValidatedMeasurement] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    canonical: CanonicalInputs | None = None
    age_years: float | None = None

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors and self.canonical is not None


def _is_real_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _unit_hint(defn: BiomarkerDef, value: float, used_unit: str) -> str:
    """Suggest an alternative allowed unit under which ``value`` would be plausible."""
    hints = [
        c.unit
        for c in defn.conversions
        if c.unit != used_unit and defn.plausible_low <= value * c.factor <= defn.plausible_high
    ]
    return f"；请核对单位，数值更符合 {', '.join(hints)}" if hints else ""


def _validate_one(
    defn: BiomarkerDef,
    raw: RawMeasurement | None,
    lod_policy: LodPolicy,
    issues: list[Issue],
) -> ValidatedMeasurement:
    f = defn.code.value
    vm = ValidatedMeasurement(
        code=f,
        original_value=raw.value if raw else None,
        original_unit=raw.unit if raw else None,
        normalised_unit=None,
        canonical_value=None,
        canonical_unit=defn.canonical_unit,
        conversion_factor=None,
        quality_status=QualityStatus.MISSING,
        reference_low=defn.reference_low,
        reference_high=defn.reference_high,
        below_lod=bool(raw.below_lod) if raw else False,
        collected_on=raw.collected_on if raw else None,
    )

    if raw is None or (raw.value is None and not raw.below_lod):
        issues.append(Issue("MISSING_VALUE", f, f"缺少必需指标：{defn.name_zh} ({defn.name_en})"))
        return vm

    # --- unit -----------------------------------------------------------
    try:
        unit = normalise_unit(raw.unit)
        # Probe conversion with 1.0 to validate the unit is allowed.
        _, factor = convert(1.0, unit, defn.canonical_unit, defn.conversions)
    except UnitError as e:
        vm.quality_status = QualityStatus.UNIT_ERROR
        issues.append(Issue(e.code, f, f"{defn.name_zh}: {e.message}"))
        return vm
    vm.normalised_unit = unit
    vm.conversion_factor = factor

    # --- below limit of detection (CRP only) ----------------------------
    if raw.below_lod:
        if defn.code is not BiomarkerCode.CRP:
            vm.quality_status = QualityStatus.INVALID_VALUE
            issues.append(Issue("LOD_NOT_SUPPORTED", f, f"{defn.name_zh} 不支持“低于检出限”标记"))
            return vm
        if not _is_real_number(raw.lod) or raw.lod is None or raw.lod <= 0:
            vm.quality_status = QualityStatus.INVALID_VALUE
            issues.append(
                Issue(
                    "LOD_REQUIRED",
                    f,
                    "CRP 标记为低于检出限时必须提供大于 0 的检出限 (lod)，单位与结果单位相同",
                )
            )
            return vm
        lod_c = raw.lod * factor
        vm.lod_canonical = lod_c
        if not (defn.plausible_low <= lod_c <= defn.plausible_high):
            vm.quality_status = QualityStatus.IMPLAUSIBLE
            issues.append(
                Issue(
                    "LOD_IMPLAUSIBLE",
                    f,
                    f"CRP 检出限换算后为 {lod_c:g} mg/dL，超出可接受范围 "
                    f"[{defn.plausible_low:g}, {defn.plausible_high:g}] mg/dL" + _unit_hint(defn, raw.lod, unit),
                )
            )
            return vm
        if raw.value is not None and _is_real_number(raw.value) and raw.value > raw.lod:
            vm.quality_status = QualityStatus.INVALID_VALUE
            issues.append(Issue("LOD_CONFLICT", f, "CRP 标记为低于检出限，但结果值大于检出限"))
            return vm
        if lod_policy is LodPolicy.REJECT:
            vm.quality_status = QualityStatus.INVALID_VALUE
            issues.append(Issue("LOD_REJECTED", f, "CRP 低于检出限，当前策略不允许替代值，无法计算"))
            return vm
        if lod_policy is LodPolicy.LOD_DIV_SQRT2:
            vm.canonical_value = lod_c / math.sqrt(2)
            vm.imputation = "lod_div_sqrt2"
        else:
            vm.canonical_value = lod_c
            vm.imputation = "lod"
        vm.quality_status = QualityStatus.BELOW_LOD_IMPUTED
        issues.append(
            Issue(
                "CRP_BELOW_LOD_IMPUTED",
                f,
                f"CRP 低于检出限，按策略 {vm.imputation} 以 {vm.canonical_value:.4g} mg/dL "
                "代入 ln(CRP)；结果不确定性增加",
                Severity.WARNING,
            )
        )
        return vm

    # --- numeric value --------------------------------------------------
    value = raw.value
    if not _is_real_number(value):
        vm.quality_status = QualityStatus.INVALID_VALUE
        issues.append(Issue("NOT_A_NUMBER", f, f"{defn.name_zh} 的数值无效（必须为有限实数）"))
        return vm
    assert value is not None
    if value < 0:
        vm.quality_status = QualityStatus.INVALID_VALUE
        issues.append(Issue("NEGATIVE_VALUE", f, f"{defn.name_zh} 不能为负数"))
        return vm
    if value == 0 and defn.code is BiomarkerCode.CRP:
        vm.quality_status = QualityStatus.INVALID_VALUE
        issues.append(
            Issue(
                "CRP_ZERO",
                f,
                "CRP 为 0 无法进行对数变换。若检测结果低于检出限，请勾选“低于检出限”并填写检出限",
            )
        )
        return vm

    canonical = value * factor
    vm.canonical_value = canonical
    if not (defn.plausible_low <= canonical <= defn.plausible_high):
        vm.quality_status = QualityStatus.IMPLAUSIBLE
        vm.canonical_value = None
        issues.append(
            Issue(
                "OUT_OF_PLAUSIBLE_RANGE",
                f,
                f"{defn.name_zh} = {value:g} {unit}（换算 {canonical:g} {defn.canonical_unit}）"
                f"超出可接受范围 [{defn.plausible_low:g}, {defn.plausible_high:g}] "
                f"{defn.canonical_unit}" + _unit_hint(defn, value, unit),
            )
        )
        return vm

    if canonical < defn.reference_low or canonical > defn.reference_high:
        vm.quality_status = QualityStatus.OUT_OF_REFERENCE_RANGE
        issues.append(
            Issue(
                "OUT_OF_REFERENCE_RANGE",
                f,
                f"{defn.name_zh} 超出通用参考区间 [{defn.reference_low:g}, "
                f"{defn.reference_high:g}] {defn.canonical_unit}（仅提示，非诊断）",
                Severity.WARNING,
            )
        )
    else:
        vm.quality_status = QualityStatus.VALID
    return vm


def validate_measurement(
    code: str, raw: RawMeasurement | None, lod_policy: LodPolicy = DEFAULT_LOD_POLICY
) -> tuple[ValidatedMeasurement | None, list[Issue]]:
    """Validate a single measurement (used when storing lab results)."""
    issues: list[Issue] = []
    try:
        defn = BIOMARKERS[BiomarkerCode(code)]
    except ValueError:
        return None, [Issue("UNKNOWN_BIOMARKER", code, f"未知指标 '{code}'")]
    vm = _validate_one(defn, raw, lod_policy, issues)
    if raw is not None and raw.collected_on and raw.collected_on > date.today():
        issues.append(Issue("FUTURE_DATE", code, "检测日期不能晚于今天"))
    return vm, issues


def validate_inputs(
    measurements: dict[str, RawMeasurement | None],
    age_years: float | None,
    *,
    lod_policy: LodPolicy = DEFAULT_LOD_POLICY,
    max_lab_span_days: int = DEFAULT_MAX_LAB_SPAN_DAYS,
    today: date | None = None,
) -> ValidationReport:
    report = ValidationReport()
    issues = report.issues

    known = {c.value for c in BiomarkerCode}
    for extra in sorted(set(measurements) - known):
        issues.append(Issue("UNKNOWN_BIOMARKER", extra, f"未知指标 '{extra}'"))

    for code, defn in BIOMARKERS.items():
        report.measurements[code.value] = _validate_one(defn, measurements.get(code.value), lod_policy, issues)

    # --- chronological age ------------------------------------------------
    if age_years is None:
        issues.append(Issue("MISSING_VALUE", "age", "缺少实际年龄"))
    elif not _is_real_number(age_years):
        issues.append(Issue("NOT_A_NUMBER", "age", "实际年龄必须为有限实数"))
    elif not (AGE_HARD_LOW <= age_years <= AGE_HARD_HIGH):
        issues.append(
            Issue(
                "OUT_OF_PLAUSIBLE_RANGE",
                "age",
                f"实际年龄须在 [{AGE_HARD_LOW:g}, {AGE_HARD_HIGH:g}] 岁之间",
            )
        )
    else:
        report.age_years = float(age_years)
        if not (AGE_TRAINING_LOW <= age_years <= AGE_TRAINING_HIGH):
            issues.append(
                Issue(
                    "AGE_OUTSIDE_TRAINING_RANGE",
                    "age",
                    f"年龄超出模型训练人群范围 [{AGE_TRAINING_LOW:g}, {AGE_TRAINING_HIGH:g}] 岁，外推结果可靠性降低",
                    Severity.WARNING,
                )
            )

    # --- collection dates -------------------------------------------------
    ref_day = today or date.today()
    dates = [m.collected_on for m in measurements.values() if m and m.collected_on]
    for key, m in measurements.items():
        if m and m.collected_on and m.collected_on > ref_day:
            issues.append(Issue("FUTURE_DATE", key, "检测日期不能晚于今天"))
    if dates:
        span = (max(dates) - min(dates)).days
        if span > max_lab_span_days:
            issues.append(
                Issue(
                    "LAB_DATES_SPAN_TOO_WIDE",
                    "collected_on",
                    f"各指标检测日期相差 {span} 天，超过允许的 {max_lab_span_days} 天",
                )
            )
        if len(dates) < len(BIOMARKERS):
            issues.append(
                Issue(
                    "COLLECTION_DATE_INCOMPLETE",
                    "collected_on",
                    "部分指标缺少检测日期",
                    Severity.WARNING,
                )
            )
    else:
        issues.append(Issue("COLLECTION_DATE_MISSING", "collected_on", "未提供检测日期", Severity.WARNING))

    if report.errors:
        return report

    cv = {k: v.canonical_value for k, v in report.measurements.items()}
    assert all(v is not None for v in cv.values()) and report.age_years is not None
    report.canonical = CanonicalInputs(
        albumin_g_l=cv["albumin"],  # type: ignore[arg-type]
        creatinine_umol_l=cv["creatinine"],  # type: ignore[arg-type]
        glucose_mmol_l=cv["glucose"],  # type: ignore[arg-type]
        crp_mg_dl=cv["crp"],  # type: ignore[arg-type]
        lymphocyte_pct=cv["lymphocyte_pct"],  # type: ignore[arg-type]
        mcv_fl=cv["mcv"],  # type: ignore[arg-type]
        rdw_pct=cv["rdw"],  # type: ignore[arg-type]
        alp_u_l=cv["alp"],  # type: ignore[arg-type]
        wbc_10e3_ul=cv["wbc"],  # type: ignore[arg-type]
        age_years=report.age_years,
    )
    return report
