"""Structured intake for one BHRT evaluation."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sex = Literal["female", "male"]
ReproStage = Literal["cycling", "perimenopause", "postmenopause", "surgical_or_poi", "unknown"]
Bleeding = Literal["none", "evaluated_benign", "undiagnosed"]
RoutePref = Literal["no_preference", "cream", "pellet"]
ProgPref = Literal["auto", "oral", "vaginal", "cream"]
SleepApnea = Literal["no", "treated", "untreated", "unknown"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabValue(_M):
    code: str = Field(min_length=1, max_length=32)
    value: float
    unit: str | None = Field(default=None, max_length=32)
    collected_on: date | None = None
    below_detection: bool = False


class BreastImaging(_M):
    performed_on: date | None = None
    modality: Literal["mammogram", "ultrasound", "both"] = "ultrasound"
    birads: int | None = Field(default=None, ge=0, le=6)


class PelvicUltrasound(_M):
    performed_on: date | None = None
    endometrial_thickness_mm: float | None = Field(default=None, ge=0, le=60)
    fibroids: bool = False
    other_findings: str | None = Field(default=None, max_length=500)


class History(_M):
    breast_cancer: bool = False
    endometrial_cancer: bool = False
    ovarian_cancer: bool = False
    vte: bool = False  # VTE / PE history
    vte_active: bool = False
    thrombophilia: bool = False
    vte_cleared_by_specialist: bool = False  # hematology/cardiology cleared -> transdermal only
    liver_cleared_by_specialist: bool = False  # hepatology cleared
    stroke_mi: bool = False
    liver_disease_active: bool = False
    autoimmune_liver_antibody_positive: bool = False
    migraine_with_aura: bool = False
    gallbladder_disease: bool = False
    fibroids: bool = False
    endometriosis: bool = False
    # men
    prostate_cancer: bool = False
    abnormal_dre: bool = False
    sleep_apnea: SleepApnea = "unknown"
    desires_fertility: bool = False


class FamilyHistory(_M):
    breast_cancer_first_degree: bool = False
    breast_cancer_early_onset: bool = False
    brca_carrier: bool = False
    thrombophilia: bool = False


class Medications(_M):
    anticoagulant: bool = False
    tamoxifen_or_ai: bool = False
    thyroid_hormone: bool = False
    ssri_snri: bool = False
    current_hrt: str | None = Field(default=None, max_length=300)
    stable_on_transdermal: bool = False  # documented stable response on cream (pellet prerequisite)
    other: str | None = Field(default=None, max_length=500)


class Preferences(_M):
    route: RoutePref = "no_preference"
    progesterone: ProgPref = "auto"
    biest_ratio: Literal["2:8", "1:9"] = "2:8"
    # add transdermal progesterone cream on top of oral/vaginal protection (option & supplement)
    progesterone_cream_supplement: bool = False
    poor_daily_adherence: bool = False
    pellet_consent_signed: bool = False


class BhrtIntake(_M):
    client_ref: str = Field(min_length=1, max_length=64)
    sex: Sex
    age: int = Field(ge=18, le=100)
    height_cm: float | None = Field(default=None, ge=100, le=230)
    weight_kg: float | None = Field(default=None, ge=25, le=300)
    bp_systolic: int | None = Field(default=None, ge=60, le=260)
    bp_diastolic: int | None = Field(default=None, ge=30, le=160)
    smoker: bool = False

    # women
    repro_stage: ReproStage = "unknown"
    years_since_fmp: float | None = Field(default=None, ge=0, le=60)
    uterus_intact: bool | None = None
    abnormal_bleeding: Bleeding = "none"

    # symptoms: MRS 11 items (0-4) for women, ADAM 10 yes/no for men
    mrs: list[int] | None = Field(default=None, min_length=11, max_length=11)
    adam: list[bool] | None = Field(default=None, min_length=10, max_length=10)
    top_complaints: list[str] = Field(default_factory=list, max_length=3)
    hsdd_confirmed: bool = False  # distressing low libido after relationship / SSRI / GSM pain reviewed

    history: History = Field(default_factory=History)
    family: FamilyHistory = Field(default_factory=FamilyHistory)
    medications: Medications = Field(default_factory=Medications)

    labs: list[LabValue] = Field(default_factory=list, max_length=100)
    # second morning total T for men (two low values are required for diagnosis)
    male_total_t_repeat: LabValue | None = None
    breast_imaging: BreastImaging | None = None
    pelvic_us: PelvicUltrasound | None = None
    dexa_t_score: float | None = Field(default=None, ge=-6, le=6)
    # panel imaging items completed (codes from panel.IMAGING_ITEMS, e.g. "us_thyroid", "mri_brain")
    imaging_done: list[str] = Field(default_factory=list, max_length=20)

    preferences: Preferences = Field(default_factory=Preferences)
    evaluation_date: date | None = None
    start_date: date | None = None
