"""Levine Clinical PhenoAge (2018) - deterministic reference engine.

Source
------
Levine ME, Lu AT, Quach A, et al. "An epigenetic biomarker of aging for
lifespan and healthspan." Aging (Albany NY). 2018;10(4):573-591.
doi:10.18632/aging.101414 (Table 1 / Methods: "Phenotypic Age").

Model (canonical units, see app.domain.biomarkers):

    xb = -19.907
         - 0.0336  * albumin [g/L]
         + 0.0095  * creatinine [umol/L]
         + 0.1953  * glucose [mmol/L]
         + 0.0954  * ln(CRP [mg/dL])
         - 0.0120  * lymphocyte [%]
         + 0.0268  * MCV [fL]
         + 0.3306  * RDW [%]
         + 0.00188 * ALP [U/L]
         + 0.0554  * WBC [10^3 cells/uL]
         + 0.0804  * chronological age [years]

    M (10-year / 120-month mortality score, Gompertz, gamma = 0.0076927)
      = 1 - exp( -exp(xb) * (exp(120 * gamma) - 1) / gamma )

    PhenoAge = 141.50225 + ln( -0.00553 * ln(1 - M) ) / 0.090165

Numerical note: ``ln(1 - M)`` equals ``-H`` where
``H = exp(xb) * (exp(120*gamma) - 1) / gamma`` is the cumulative hazard. We
evaluate PhenoAge through ``H`` directly, which is algebraically identical to
the published formula but does not lose precision when M approaches 1
(1 - M underflows to 0 in floating point for very high-risk inputs). The
literal published form is also computed and checked in the unit tests.

This module performs **no** I/O, no randomness and no model inference other
than the closed-form equation above. It must never call an LLM.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from app.domain.biomarkers import BiomarkerCode

MODEL_ID = "levine_phenoage_2018"
MODEL_VERSION = "1.0.0"
ALGORITHM_SOURCE = (
    "Levine ME, et al. An epigenetic biomarker of aging for lifespan and healthspan. "
    "Aging (Albany NY). 2018;10(4):573-591. doi:10.18632/aging.101414"
)

INTERCEPT = -19.907
COEFFICIENTS: dict[str, float] = {
    BiomarkerCode.ALBUMIN.value: -0.0336,
    BiomarkerCode.CREATININE.value: 0.0095,
    BiomarkerCode.GLUCOSE.value: 0.1953,
    "ln_crp": 0.0954,
    BiomarkerCode.LYMPHOCYTE_PCT.value: -0.0120,
    BiomarkerCode.MCV.value: 0.0268,
    BiomarkerCode.RDW.value: 0.3306,
    BiomarkerCode.ALP.value: 0.00188,
    BiomarkerCode.WBC.value: 0.0554,
    "age": 0.0804,
}
GAMMA = 0.0076927
HORIZON_MONTHS = 120.0
PHENOAGE_A = 141.50225
PHENOAGE_B = -0.00553
PHENOAGE_C = 0.090165


def coefficients_fingerprint() -> str:
    """SHA-256 over all model constants; stored with every result for traceability."""
    payload = {
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "intercept": INTERCEPT,
        "coefficients": COEFFICIENTS,
        "gamma": GAMMA,
        "horizon_months": HORIZON_MONTHS,
        "phenoage": [PHENOAGE_A, PHENOAGE_B, PHENOAGE_C],
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


class PhenoAgeComputationError(ArithmeticError):
    """Raised when the equation cannot produce a finite, meaningful value."""


@dataclass(frozen=True)
class CanonicalInputs:
    """All values already validated and expressed in canonical units."""

    albumin_g_l: float
    creatinine_umol_l: float
    glucose_mmol_l: float
    crp_mg_dl: float
    lymphocyte_pct: float
    mcv_fl: float
    rdw_pct: float
    alp_u_l: float
    wbc_10e3_ul: float
    age_years: float


@dataclass(frozen=True)
class PhenoAgeOutput:
    phenoage: float
    linear_predictor: float  # xb
    mortality_score: float  # M, 120-month mortality risk
    cumulative_hazard: float  # H = -ln(1 - M)
    ln_crp: float
    terms: dict[str, float]  # per-term contributions to xb


def linear_predictor(x: CanonicalInputs) -> tuple[float, float, dict[str, float]]:
    if x.crp_mg_dl <= 0 or not math.isfinite(x.crp_mg_dl):
        raise PhenoAgeComputationError("CRP must be > 0 mg/dL before log transform")
    ln_crp = math.log(x.crp_mg_dl)
    c = COEFFICIENTS
    terms = {
        "intercept": INTERCEPT,
        "albumin": c["albumin"] * x.albumin_g_l,
        "creatinine": c["creatinine"] * x.creatinine_umol_l,
        "glucose": c["glucose"] * x.glucose_mmol_l,
        "ln_crp": c["ln_crp"] * ln_crp,
        "lymphocyte_pct": c["lymphocyte_pct"] * x.lymphocyte_pct,
        "mcv": c["mcv"] * x.mcv_fl,
        "rdw": c["rdw"] * x.rdw_pct,
        "alp": c["alp"] * x.alp_u_l,
        "wbc": c["wbc"] * x.wbc_10e3_ul,
        "age": c["age"] * x.age_years,
    }
    xb = math.fsum(terms.values())
    return xb, ln_crp, terms


def compute_phenoage(x: CanonicalInputs) -> PhenoAgeOutput:
    for name, v in vars(x).items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            raise PhenoAgeComputationError(f"non-finite canonical input: {name}")

    xb, ln_crp, terms = linear_predictor(x)

    # Cumulative 120-month Gompertz hazard: H = exp(xb) * (exp(120*gamma) - 1) / gamma
    try:
        hazard = math.exp(xb) * math.expm1(HORIZON_MONTHS * GAMMA) / GAMMA
    except OverflowError as exc:  # pragma: no cover - guarded by input ranges
        raise PhenoAgeComputationError("hazard overflow") from exc
    if not (hazard > 0 and math.isfinite(hazard)):
        raise PhenoAgeComputationError("hazard is not a positive finite number")

    mortality = -math.expm1(-hazard)  # M = 1 - exp(-H)

    # PhenoAge = A + ln(B * ln(1 - M)) / C  with ln(1 - M) = -H
    inner = PHENOAGE_B * (-hazard)
    if not inner > 0:
        raise PhenoAgeComputationError("log argument non-positive")
    phenoage = PHENOAGE_A + math.log(inner) / PHENOAGE_C
    if not math.isfinite(phenoage):
        raise PhenoAgeComputationError("PhenoAge is not finite")

    return PhenoAgeOutput(
        phenoage=phenoage,
        linear_predictor=xb,
        mortality_score=mortality,
        cumulative_hazard=hazard,
        ln_crp=ln_crp,
        terms=terms,
    )


def compute_phenoage_literal(x: CanonicalInputs) -> float:
    """Literal transcription of the published equations (used only in tests).

    May fail (log of 0) for extreme inputs where 1 - M underflows.
    """
    xb, _, _ = linear_predictor(x)
    m = 1 - math.exp(-math.exp(xb) * (math.exp(120 * GAMMA) - 1) / GAMMA)
    return PHENOAGE_A + math.log(PHENOAGE_B * math.log(1 - m)) / PHENOAGE_C
