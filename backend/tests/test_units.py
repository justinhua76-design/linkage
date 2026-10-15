import pytest

from app.domain.biomarkers import BIOMARKERS, BiomarkerCode
from app.domain.units import UnitError, convert, normalise_unit


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("g/L", "g/L"),
        (" g / dl ", "g/dL"),
        ("µmol/L", "umol/L"),  # micro sign U+00B5
        ("μmol/L", "umol/L"),  # greek mu U+03BC
        ("umol/l", "umol/L"),
        ("mg/dL", "mg/dL"),
        ("MG/L", "mg/L"),
        ("10^9/L", "10^9/L"),
        ("×10^9/L", "10^9/L"),
        ("K/uL", "10^3/uL"),
        ("IU/L", "U/L"),
        ("fl", "fL"),
        ("％", "%"),  # full-width percent (NFKC)
    ],
)
def test_normalise_unit_aliases(raw, expected):
    assert normalise_unit(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "mg", "mmol", "g/l/l", "mg/dl2", "ng/mL", "mEq/L"])
def test_unknown_units_rejected(raw):
    with pytest.raises(UnitError):
        normalise_unit(raw)


def _conv(code, value, unit):
    d = BIOMARKERS[code]
    return convert(value, normalise_unit(unit), d.canonical_unit, d.conversions)[0]


def test_crp_mg_l_to_mg_dl():
    assert _conv(BiomarkerCode.CRP, 3.0, "mg/L") == pytest.approx(0.3)
    assert _conv(BiomarkerCode.CRP, 0.3, "mg/dL") == pytest.approx(0.3)


def test_documented_conversion_factors():
    assert _conv(BiomarkerCode.ALBUMIN, 4.5, "g/dL") == pytest.approx(45.0)
    assert _conv(BiomarkerCode.CREATININE, 1.0, "mg/dL") == pytest.approx(88.4)
    assert _conv(BiomarkerCode.GLUCOSE, 100, "mg/dL") == pytest.approx(5.551)
    assert _conv(BiomarkerCode.ALP, 1.0, "ukat/L") == pytest.approx(60.0)
    assert _conv(BiomarkerCode.WBC, 6500, "cells/uL") == pytest.approx(6.5)
    assert _conv(BiomarkerCode.WBC, 6.5, "10^9/L") == pytest.approx(6.5)


@pytest.mark.parametrize(
    "code,unit",
    [
        (BiomarkerCode.RDW, "fL"),  # RDW-SD is a different quantity
        (BiomarkerCode.CRP, "mmol/L"),
        (BiomarkerCode.ALBUMIN, "mg/dL"),
        (BiomarkerCode.GLUCOSE, "g/L"),
        (BiomarkerCode.LYMPHOCYTE_PCT, "10^9/L"),  # absolute count is not a percentage
        (BiomarkerCode.MCV, "%"),
    ],
)
def test_wrong_quantity_units_rejected(code, unit):
    with pytest.raises(UnitError) as e:
        _conv(code, 1.0, unit)
    assert e.value.code == "UNIT_NOT_ALLOWED"
