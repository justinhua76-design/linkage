"""Algorithm tests: agreement with independent reference, invariants, determinism."""

import json
import math
import random
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain import phenoage as engine
from app.domain.phenoage import CanonicalInputs, compute_phenoage, compute_phenoage_literal
from tests.reference_impl import reference_phenoage

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "phenoage_reference_cases.json").read_text())
# Agreed numerical tolerance between the engine and the independent reference.
# Display precision is 0.1 year; we require 6 orders of magnitude tighter.
TOL_YEARS = 1e-6
TOL_MORTALITY = 1e-9


def to_canonical(d: dict) -> CanonicalInputs:
    return CanonicalInputs(
        albumin_g_l=d["albumin"],
        creatinine_umol_l=d["creatinine"],
        glucose_mmol_l=d["glucose"],
        crp_mg_dl=d["crp"],
        lymphocyte_pct=d["lymphocyte_pct"],
        mcv_fl=d["mcv"],
        rdw_pct=d["rdw"],
        alp_u_l=d["alp"],
        wbc_10e3_ul=d["wbc"],
        age_years=d["age"],
    )


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=[c["id"] for c in FIXTURE["cases"]])
def test_matches_independent_reference_fixture(case):
    out = compute_phenoage(to_canonical(case["inputs"]))
    assert abs(out.phenoage - float(case["expected_phenoage"])) < TOL_YEARS
    assert abs(out.mortality_score - float(case["expected_mortality_score"])) < TOL_MORTALITY
    assert abs(out.linear_predictor - float(case["expected_xb"])) < 1e-9


def test_fixture_still_matches_reference_impl():
    """Guards against the fixture file being edited by hand."""
    for case in FIXTURE["cases"][:4]:
        pa, _, _ = reference_phenoage(case["inputs"])
        assert abs(pa - Decimal(case["expected_phenoage"])) < Decimal("1e-11")


def _random_profile(rng: random.Random) -> dict:
    return dict(
        albumin=rng.uniform(30, 52),
        creatinine=rng.uniform(40, 150),
        glucose=rng.uniform(3.5, 10),
        crp=math.exp(rng.uniform(math.log(0.01), math.log(5))),
        lymphocyte_pct=rng.uniform(10, 50),
        mcv=rng.uniform(75, 105),
        rdw=rng.uniform(11, 17),
        alp=rng.uniform(30, 150),
        wbc=rng.uniform(3, 12),
        age=rng.uniform(20, 84),
    )


def test_random_profiles_against_reference():
    rng = random.Random(20180417)  # fixed seed -> deterministic test
    for _ in range(200):
        p = _random_profile(rng)
        pa, m, _ = reference_phenoage(p)
        out = compute_phenoage(to_canonical(p))
        assert abs(out.phenoage - float(pa)) < TOL_YEARS
        assert abs(out.mortality_score - float(m)) < TOL_MORTALITY


def test_stable_form_equals_literal_published_form():
    rng = random.Random(7)
    for _ in range(200):
        x = to_canonical(_random_profile(rng))
        assert compute_phenoage(x).phenoage == pytest.approx(compute_phenoage_literal(x), abs=1e-8)


def test_extreme_profile_stable_where_literal_fails():
    case = next(c for c in FIXTURE["cases"] if c["id"] == "REF-05")
    x = to_canonical(case["inputs"])
    with pytest.raises(ValueError):  # math domain error: ln(0)
        compute_phenoage_literal(x)
    out = compute_phenoage(x)
    assert math.isfinite(out.phenoage)
    assert abs(out.phenoage - float(case["expected_phenoage"])) < TOL_YEARS


def test_published_constants_are_unchanged():
    assert engine.INTERCEPT == -19.907
    assert engine.COEFFICIENTS == {
        "albumin": -0.0336,
        "creatinine": 0.0095,
        "glucose": 0.1953,
        "ln_crp": 0.0954,
        "lymphocyte_pct": -0.0120,
        "mcv": 0.0268,
        "rdw": 0.3306,
        "alp": 0.00188,
        "wbc": 0.0554,
        "age": 0.0804,
    }
    assert (engine.GAMMA, engine.PHENOAGE_A, engine.PHENOAGE_B, engine.PHENOAGE_C) == (
        0.0076927,
        141.50225,
        -0.00553,
        0.090165,
    )
    # (exp(120*gamma) - 1) == 1.51714 as printed in the 2019 correction
    assert math.expm1(120 * engine.GAMMA) == pytest.approx(1.51714, abs=5e-6)


def test_coefficient_fingerprint_is_stable():
    assert engine.coefficients_fingerprint() == engine.coefficients_fingerprint()
    assert len(engine.coefficients_fingerprint()) == 64


@pytest.mark.parametrize(
    "field,delta,direction",
    [
        ("albumin_g_l", 5, -1),
        ("creatinine_umol_l", 20, +1),
        ("glucose_mmol_l", 1, +1),
        ("crp_mg_dl", 0.5, +1),
        ("lymphocyte_pct", 5, -1),
        ("mcv_fl", 5, +1),
        ("rdw_pct", 1, +1),
        ("alp_u_l", 20, +1),
        ("wbc_10e3_ul", 1, +1),
        ("age_years", 5, +1),
    ],
)
def test_monotonic_direction_matches_coefficient_sign(field, delta, direction):
    base = to_canonical(FIXTURE["cases"][0]["inputs"])
    bumped = CanonicalInputs(**{**vars(base), field: getattr(base, field) + delta})
    diff = compute_phenoage(bumped).phenoage - compute_phenoage(base).phenoage
    assert diff * direction > 0


def test_one_year_of_age_adds_roughly_0_89_phenoage_years():
    # dPhenoAge/dAge = 0.0804 / 0.090165 when M is small
    base = to_canonical(FIXTURE["cases"][0]["inputs"])
    older = CanonicalInputs(**{**vars(base), "age_years": base.age_years + 1})
    d = compute_phenoage(older).phenoage - compute_phenoage(base).phenoage
    assert d == pytest.approx(0.0804 / 0.090165, rel=1e-9)


def test_deterministic():
    x = to_canonical(FIXTURE["cases"][2]["inputs"])
    results = {compute_phenoage(x).phenoage for _ in range(100)}
    assert len(results) == 1


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_engine_refuses_invalid_crp(bad):
    x = CanonicalInputs(**{**vars(to_canonical(FIXTURE["cases"][0]["inputs"])), "crp_mg_dl": bad})
    with pytest.raises(engine.PhenoAgeComputationError):
        compute_phenoage(x)


def test_engine_refuses_non_finite_inputs():
    x = CanonicalInputs(**{**vars(to_canonical(FIXTURE["cases"][0]["inputs"])), "mcv_fl": float("nan")})
    with pytest.raises(engine.PhenoAgeComputationError):
        compute_phenoage(x)


def test_no_llm_dependencies():
    """Ages must come from the deterministic engine only - no LLM SDKs in the app."""
    app_dir = Path(__file__).parents[1] / "app"
    banned = ("openai", "anthropic", "langchain", "transformers", "google.generativeai", "llama")
    for py in app_dir.rglob("*.py"):
        text = py.read_text()
        for b in banned:
            assert f"import {b}" not in text and f"from {b}" not in text, f"{py} imports {b}"
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text().lower()
    for b in banned:
        assert f'"{b}' not in pyproject
