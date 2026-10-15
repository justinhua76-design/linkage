"""Biomarker registry for Levine Clinical PhenoAge (2018).

Canonical units are the units in which the Levine et al. (2018) model was
fitted (NHANES III, SI units except CRP which is mg/dL, natural-log
transformed). See docs/CLINICAL_MODEL.md for sources of every number below.

Two kinds of ranges are defined:

* ``plausible`` - hard physiological/analytical limits. Values outside are
  treated as data-entry or unit errors and **block** computation.
* ``reference`` - typical adult reference interval. Values outside are
  accepted but flagged ``OUT_OF_REFERENCE_RANGE`` (informational only,
  not a diagnosis). Lab-supplied reference ranges take precedence for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.units import Conversion


class BiomarkerCode(StrEnum):
    ALBUMIN = "albumin"
    CREATININE = "creatinine"
    GLUCOSE = "glucose"
    CRP = "crp"
    LYMPHOCYTE_PCT = "lymphocyte_pct"
    MCV = "mcv"
    RDW = "rdw"
    ALP = "alp"
    WBC = "wbc"


@dataclass(frozen=True)
class BiomarkerDef:
    code: BiomarkerCode
    name_en: str
    name_zh: str
    canonical_unit: str
    conversions: tuple[Conversion, ...]
    plausible_low: float  # inclusive, canonical unit
    plausible_high: float  # inclusive, canonical unit
    reference_low: float
    reference_high: float
    strictly_positive: bool = False
    notes: str = ""

    @property
    def allowed_units(self) -> list[str]:
        return [c.unit for c in self.conversions]


BIOMARKERS: dict[BiomarkerCode, BiomarkerDef] = {
    BiomarkerCode.ALBUMIN: BiomarkerDef(
        code=BiomarkerCode.ALBUMIN,
        name_en="Albumin",
        name_zh="白蛋白",
        canonical_unit="g/L",
        conversions=(Conversion("g/L", 1.0), Conversion("g/dL", 10.0, "1 g/dL = 10 g/L")),
        plausible_low=10.0,
        plausible_high=70.0,
        reference_low=35.0,
        reference_high=52.0,
    ),
    BiomarkerCode.CREATININE: BiomarkerDef(
        code=BiomarkerCode.CREATININE,
        name_en="Creatinine",
        name_zh="肌酐",
        canonical_unit="umol/L",
        conversions=(
            Conversion("umol/L", 1.0),
            Conversion("mg/dL", 88.4, "NHANES SI factor: 1 mg/dL = 88.4 umol/L"),
        ),
        plausible_low=10.0,
        plausible_high=2000.0,
        reference_low=45.0,
        reference_high=110.0,
    ),
    BiomarkerCode.GLUCOSE: BiomarkerDef(
        code=BiomarkerCode.GLUCOSE,
        name_en="Fasting glucose",
        name_zh="空腹血糖",
        canonical_unit="mmol/L",
        conversions=(
            Conversion("mmol/L", 1.0),
            Conversion("mg/dL", 0.05551, "NHANES SI factor: 1 mg/dL = 0.05551 mmol/L"),
        ),
        plausible_low=1.0,
        plausible_high=40.0,
        reference_low=3.9,
        reference_high=6.1,
    ),
    BiomarkerCode.CRP: BiomarkerDef(
        code=BiomarkerCode.CRP,
        name_en="C-reactive protein",
        name_zh="C反应蛋白",
        canonical_unit="mg/dL",
        conversions=(
            Conversion("mg/dL", 1.0),
            Conversion("mg/L", 0.1, "1 mg/L = 0.1 mg/dL; model uses ln(CRP in mg/dL)"),
        ),
        # 0.001 mg/dL (= 0.01 mg/L) lower bound for a *measured* value; anything
        # lower must be reported as below the limit of detection (LOD).
        # Upper limit 50 mg/dL (= 500 mg/L).
        plausible_low=0.001,
        plausible_high=50.0,
        reference_low=0.0,
        reference_high=0.5,
        strictly_positive=True,
        notes="Model term is ln(CRP[mg/dL]); zero/below-LOD handled explicitly.",
    ),
    BiomarkerCode.LYMPHOCYTE_PCT: BiomarkerDef(
        code=BiomarkerCode.LYMPHOCYTE_PCT,
        name_en="Lymphocyte percent",
        name_zh="淋巴细胞百分比",
        canonical_unit="%",
        conversions=(Conversion("%", 1.0),),
        plausible_low=1.0,
        plausible_high=99.0,
        reference_low=20.0,
        reference_high=40.0,
        notes="Percentage of WBC, NOT absolute lymphocyte count; fractions (0-1) rejected.",
    ),
    BiomarkerCode.MCV: BiomarkerDef(
        code=BiomarkerCode.MCV,
        name_en="Mean corpuscular volume",
        name_zh="平均红细胞体积",
        canonical_unit="fL",
        conversions=(Conversion("fL", 1.0),),
        plausible_low=50.0,
        plausible_high=150.0,
        reference_low=80.0,
        reference_high=100.0,
    ),
    BiomarkerCode.RDW: BiomarkerDef(
        code=BiomarkerCode.RDW,
        name_en="Red cell distribution width (RDW-CV)",
        name_zh="红细胞分布宽度 (RDW-CV)",
        canonical_unit="%",
        conversions=(Conversion("%", 1.0),),
        plausible_low=8.0,
        plausible_high=40.0,
        reference_low=11.5,
        reference_high=14.5,
        notes="RDW-CV in %. RDW-SD (fL) is a different quantity and is rejected.",
    ),
    BiomarkerCode.ALP: BiomarkerDef(
        code=BiomarkerCode.ALP,
        name_en="Alkaline phosphatase",
        name_zh="碱性磷酸酶",
        canonical_unit="U/L",
        conversions=(
            Conversion("U/L", 1.0),
            Conversion("ukat/L", 60.0, "1 ukat/L = 60 U/L"),
        ),
        plausible_low=5.0,
        plausible_high=2000.0,
        reference_low=40.0,
        reference_high=130.0,
    ),
    BiomarkerCode.WBC: BiomarkerDef(
        code=BiomarkerCode.WBC,
        name_en="White blood cell count",
        name_zh="白细胞计数",
        canonical_unit="10^3/uL",
        conversions=(
            Conversion("10^3/uL", 1.0),
            Conversion("10^9/L", 1.0, "10^9/L == 10^3/uL"),
            Conversion("cells/uL", 0.001, "1000 cells/uL = 1 x10^3/uL"),
        ),
        plausible_low=0.5,
        plausible_high=100.0,
        reference_low=4.0,
        reference_high=10.0,
    ),
}

# Chronological age limits. Levine 2018 was trained on NHANES III adults aged
# 20-84 (top-coded 90). Outside the training range we warn; outside the hard
# range we reject.
AGE_HARD_LOW = 18.0
AGE_HARD_HIGH = 110.0
AGE_TRAINING_LOW = 20.0
AGE_TRAINING_HIGH = 84.0
