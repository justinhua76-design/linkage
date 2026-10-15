"""Validation, missing data, CRP/LOD and boundary-value tests."""

import math
from datetime import date, timedelta

import pytest

from app.domain.biomarkers import BIOMARKERS, BiomarkerCode
from app.domain.phenoage import compute_phenoage
from app.domain.validation import (
    LodPolicy,
    QualityStatus,
    RawMeasurement,
    validate_inputs,
)

TODAY = date(2026, 10, 15)


def base_si() -> dict[str, RawMeasurement]:
    d = TODAY - timedelta(days=2)
    return {
        "albumin": RawMeasurement(45, "g/L", collected_on=d),
        "creatinine": RawMeasurement(80, "umol/L", collected_on=d),
        "glucose": RawMeasurement(5.0, "mmol/L", collected_on=d),
        "crp": RawMeasurement(1.0, "mg/L", collected_on=d),
        "lymphocyte_pct": RawMeasurement(30, "%", collected_on=d),
        "mcv": RawMeasurement(90, "fL", collected_on=d),
        "rdw": RawMeasurement(13, "%", collected_on=d),
        "alp": RawMeasurement(70, "U/L", collected_on=d),
        "wbc": RawMeasurement(6, "10^9/L", collected_on=d),
    }


def run(m, age=50.0, **kw):
    return validate_inputs(m, age, today=TODAY, **kw)


def codes(report):
    return {i.code for i in report.errors}


def test_valid_si_input_produces_canonical():
    r = run(base_si())
    assert r.ok and not r.errors and not r.warnings
    assert r.canonical.crp_mg_dl == pytest.approx(0.1)


def test_us_units_give_identical_phenoage():
    si = run(base_si())
    us = base_si()
    us["albumin"] = RawMeasurement(4.5, "g/dL", collected_on=us["albumin"].collected_on)
    us["creatinine"] = RawMeasurement(80 / 88.4, "mg/dL", collected_on=us["albumin"].collected_on)
    us["glucose"] = RawMeasurement(5.0 / 0.05551, "mg/dL", collected_on=us["albumin"].collected_on)
    us["crp"] = RawMeasurement(0.1, "mg/dL", collected_on=us["albumin"].collected_on)
    us["wbc"] = RawMeasurement(6000, "cells/uL", collected_on=us["albumin"].collected_on)
    r = run(us)
    assert r.ok
    assert compute_phenoage(r.canonical).phenoage == pytest.approx(compute_phenoage(si.canonical).phenoage, abs=1e-9)


def test_crp_unit_confusion_changes_result_by_ln10_term():
    """Entering mg/L value with mg/dL unit would shift xb by 0.0954*ln(10); we keep units explicit."""
    a = run(base_si())
    m = base_si()
    m["crp"] = RawMeasurement(1.0, "mg/dL", collected_on=m["crp"].collected_on)
    b = run(m)
    assert b.canonical.crp_mg_dl == pytest.approx(10 * a.canonical.crp_mg_dl)


@pytest.mark.parametrize("missing", [c.value for c in BiomarkerCode])
def test_each_missing_biomarker_blocks(missing):
    m = base_si()
    del m[missing]
    r = run(m)
    assert not r.ok and r.canonical is None
    assert any(i.code == "MISSING_VALUE" and i.field == missing for i in r.errors)
    assert r.measurements[missing].quality_status is QualityStatus.MISSING


def test_value_none_is_missing():
    m = base_si()
    m["mcv"] = RawMeasurement(None, "fL")
    assert "MISSING_VALUE" in codes(run(m))


def test_missing_age_blocks():
    r = run(base_si(), age=None)
    assert not r.ok and "MISSING_VALUE" in codes(r)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "45"])
def test_non_numeric_values_rejected(bad):
    m = base_si()
    m["albumin"] = RawMeasurement(bad, "g/L")  # type: ignore[arg-type]
    r = run(m)
    assert not r.ok and "NOT_A_NUMBER" in codes(r)


def test_negative_rejected():
    m = base_si()
    m["wbc"] = RawMeasurement(-1, "10^9/L")
    assert "NEGATIVE_VALUE" in codes(run(m))


@pytest.mark.parametrize("unit", [None, "", "furlongs", "fL"])
def test_bad_unit_blocks(unit):
    m = base_si()
    m["rdw"] = RawMeasurement(13, unit)
    r = run(m)
    assert not r.ok
    assert r.measurements["rdw"].quality_status is QualityStatus.UNIT_ERROR


def test_unit_mismatch_hint():
    m = base_si()
    m["albumin"] = RawMeasurement(4.5, "g/L")  # actually g/dL
    r = run(m)
    err = next(i for i in r.errors if i.field == "albumin")
    assert err.code == "OUT_OF_PLAUSIBLE_RANGE" and "g/dL" in err.message


def test_lymphocyte_fraction_rejected():
    m = base_si()
    m["lymphocyte_pct"] = RawMeasurement(0.3, "%")
    assert "OUT_OF_PLAUSIBLE_RANGE" in codes(run(m))


# ---------------------------------------------------------------- boundaries
@pytest.mark.parametrize("code", [c for c in BiomarkerCode])
def test_plausible_boundaries_inclusive(code):
    d = BIOMARKERS[code]
    unit = d.canonical_unit
    for v in (d.plausible_low, d.plausible_high):
        m = base_si()
        m[code.value] = RawMeasurement(v, unit)
        r = run(m)
        assert r.ok, (code, v, [i.as_dict() for i in r.errors])
    for v in (d.plausible_low * (1 - 1e-9) - 1e-12, d.plausible_high * (1 + 1e-9)):
        if v < 0:
            continue
        m = base_si()
        m[code.value] = RawMeasurement(v, unit)
        r = run(m)
        assert not r.ok, (code, v)
        assert r.measurements[code.value].quality_status in {
            QualityStatus.IMPLAUSIBLE,
            QualityStatus.INVALID_VALUE,
        }


def test_out_of_reference_range_is_warning_only():
    m = base_si()
    m["glucose"] = RawMeasurement(7.5, "mmol/L", collected_on=m["glucose"].collected_on)
    r = run(m)
    assert r.ok
    assert r.measurements["glucose"].quality_status is QualityStatus.OUT_OF_REFERENCE_RANGE
    assert any(w.code == "OUT_OF_REFERENCE_RANGE" for w in r.warnings)


@pytest.mark.parametrize(
    "age,ok,warn",
    [
        (17.99, False, False),
        (18, True, True),
        (20, True, False),
        (84, True, False),
        (84.01, True, True),
        (110, True, True),
        (110.01, False, False),
    ],
)
def test_age_boundaries(age, ok, warn):
    r = run(base_si(), age=age)
    assert r.ok is ok
    assert any(w.code == "AGE_OUTSIDE_TRAINING_RANGE" for w in r.warnings) is warn


# ---------------------------------------------------------------- CRP / LOD
def test_crp_zero_rejected_with_guidance():
    m = base_si()
    m["crp"] = RawMeasurement(0, "mg/L")
    r = run(m)
    assert not r.ok and "CRP_ZERO" in codes(r)


def test_crp_below_lod_requires_lod():
    m = base_si()
    m["crp"] = RawMeasurement(None, "mg/L", below_lod=True)
    assert "LOD_REQUIRED" in codes(run(m))


@pytest.mark.parametrize(
    "policy,expected_mg_dl",
    [(LodPolicy.LOD_DIV_SQRT2, 0.02 / math.sqrt(2)), (LodPolicy.LOD, 0.02)],
)
def test_crp_below_lod_imputation_converts_units(policy, expected_mg_dl):
    m = base_si()
    m["crp"] = RawMeasurement(None, "mg/L", below_lod=True, lod=0.2, collected_on=m["crp"].collected_on)
    r = run(m, lod_policy=policy)
    assert r.ok
    assert r.canonical.crp_mg_dl == pytest.approx(expected_mg_dl)
    assert r.measurements["crp"].quality_status is QualityStatus.BELOW_LOD_IMPUTED
    assert any(w.code == "CRP_BELOW_LOD_IMPUTED" for w in r.warnings)
    assert math.isfinite(compute_phenoage(r.canonical).phenoage)


def test_crp_below_lod_reject_policy():
    m = base_si()
    m["crp"] = RawMeasurement(None, "mg/L", below_lod=True, lod=0.2)
    r = run(m, lod_policy=LodPolicy.REJECT)
    assert not r.ok and "LOD_REJECTED" in codes(r)


def test_crp_below_lod_conflict():
    m = base_si()
    m["crp"] = RawMeasurement(0.5, "mg/L", below_lod=True, lod=0.2)
    assert "LOD_CONFLICT" in codes(run(m))


def test_crp_below_lod_value_equal_to_zero_is_fine():
    m = base_si()
    m["crp"] = RawMeasurement(0, "mg/L", below_lod=True, lod=0.2, collected_on=m["crp"].collected_on)
    assert run(m).ok


def test_lod_flag_not_allowed_for_other_markers():
    m = base_si()
    m["alp"] = RawMeasurement(None, "U/L", below_lod=True, lod=5)
    assert "LOD_NOT_SUPPORTED" in codes(run(m))


def test_crp_tiny_measured_value_must_use_lod():
    m = base_si()
    m["crp"] = RawMeasurement(0.005, "mg/L")  # 0.0005 mg/dL < 0.001
    assert "OUT_OF_PLAUSIBLE_RANGE" in codes(run(m))


# ---------------------------------------------------------------- dates / extras
def test_lab_date_span_too_wide():
    m = base_si()
    m["alp"] = RawMeasurement(70, "U/L", collected_on=TODAY - timedelta(days=100))
    assert "LAB_DATES_SPAN_TOO_WIDE" in codes(run(m))


def test_future_date_rejected():
    m = base_si()
    m["alp"] = RawMeasurement(70, "U/L", collected_on=TODAY + timedelta(days=1))
    assert "FUTURE_DATE" in codes(run(m))


def test_unknown_biomarker_rejected():
    m = base_si()
    m["hba1c"] = RawMeasurement(5.5, "%")
    assert "UNKNOWN_BIOMARKER" in codes(run(m))


def test_missing_dates_warn_only():
    m = {k: RawMeasurement(v.value, v.unit) for k, v in base_si().items()}
    r = run(m)
    assert r.ok and any(w.code == "COLLECTION_DATE_MISSING" for w in r.warnings)
