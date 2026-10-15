"""Regenerate tests/fixtures/phenoage_reference_cases.json.

Run:  python -m tests.fixtures.generate_reference_cases
The values are produced ONLY by tests/reference_impl.py (independent of the app).
"""

import json
from decimal import Decimal
from pathlib import Path

from tests.reference_impl import reference_phenoage

CASES = [
    # id, description, inputs (paper units)
    (
        "REF-01",
        "healthy middle-aged adult, all values mid reference interval",
        dict(
            albumin=45.0,
            creatinine=80.0,
            glucose=5.0,
            crp=0.1,
            lymphocyte_pct=30.0,
            mcv=90.0,
            rdw=13.0,
            alp=70.0,
            wbc=6.0,
            age=50.0,
        ),
    ),
    (
        "REF-02",
        "young adult, low inflammation",
        dict(
            albumin=48.0,
            creatinine=70.0,
            glucose=4.6,
            crp=0.03,
            lymphocyte_pct=35.0,
            mcv=88.0,
            rdw=12.2,
            alp=60.0,
            wbc=5.2,
            age=25.0,
        ),
    ),
    (
        "REF-03",
        "older adult, elevated CRP / RDW / glucose",
        dict(
            albumin=38.0,
            creatinine=110.0,
            glucose=7.8,
            crp=1.2,
            lymphocyte_pct=18.0,
            mcv=95.0,
            rdw=15.5,
            alp=110.0,
            wbc=8.5,
            age=72.0,
        ),
    ),
    (
        "REF-04",
        "NHANES-like population means (approx.), age 45",
        dict(
            albumin=42.0,
            creatinine=79.6,
            glucose=5.4,
            crp=0.3,
            lymphocyte_pct=30.5,
            mcv=89.5,
            rdw=12.8,
            alp=72.0,
            wbc=7.0,
            age=45.0,
        ),
    ),
    (
        "REF-05",
        "very high risk profile (tests numerical stability)",
        dict(
            albumin=25.0,
            creatinine=400.0,
            glucose=15.0,
            crp=10.0,
            lymphocyte_pct=8.0,
            mcv=105.0,
            rdw=20.0,
            alp=300.0,
            wbc=15.0,
            age=84.0,
        ),
    ),
    (
        "REF-06",
        "CRP at 0.01 mg/dL (low hs-CRP)",
        dict(
            albumin=46.0,
            creatinine=65.0,
            glucose=4.9,
            crp=0.01,
            lymphocyte_pct=32.0,
            mcv=91.0,
            rdw=12.5,
            alp=55.0,
            wbc=4.8,
            age=38.0,
        ),
    ),
    (
        "REF-07",
        "age 20 (lower training bound)",
        dict(
            albumin=47.0,
            creatinine=75.0,
            glucose=4.8,
            crp=0.05,
            lymphocyte_pct=33.0,
            mcv=87.0,
            rdw=12.4,
            alp=75.0,
            wbc=6.2,
            age=20.0,
        ),
    ),
    (
        "REF-08",
        "age 84 (upper training bound), mid values",
        dict(
            albumin=40.0,
            creatinine=95.0,
            glucose=5.8,
            crp=0.4,
            lymphocyte_pct=24.0,
            mcv=93.0,
            rdw=14.0,
            alp=85.0,
            wbc=6.8,
            age=84.0,
        ),
    ),
]


def main() -> None:
    out = {
        "description": "PhenoAge reference cases computed by an independent 400-digit Decimal "
        "implementation of Levine et al. 2018 (doi:10.18632/aging.101414). Inputs are synthetic, "
        "NOT patient data.",
        "units": {
            "albumin": "g/L",
            "creatinine": "umol/L",
            "glucose": "mmol/L",
            "crp": "mg/dL",
            "lymphocyte_pct": "%",
            "mcv": "fL",
            "rdw": "%",
            "alp": "U/L",
            "wbc": "10^3/uL",
            "age": "years",
        },
        "cases": [],
    }
    for cid, desc, inputs in CASES:
        pa, m, xb = reference_phenoage(inputs)
        out["cases"].append(
            {
                "id": cid,
                "description": desc,
                "inputs": inputs,
                "expected_phenoage": str(pa.quantize(Decimal("1e-12"))),
                "expected_mortality_score": str(m.quantize(Decimal("1e-15"))),
                "expected_xb": str(xb.quantize(Decimal("1e-12"))),
            }
        )
    path = Path(__file__).with_name("phenoage_reference_cases.json")
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
