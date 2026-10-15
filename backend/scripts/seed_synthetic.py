"""Seed SYNTHETIC demo patients through the public API (never real data).

Usage:
    API_BASE=http://localhost:8000 API_TOKEN=<clinician token> python scripts/seed_synthetic.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta

API = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("API_TOKEN")

PROFILES = [
    (
        "SYN-DEMO-001",
        "female",
        "1976-04-12",
        50,
        {
            "albumin": (4.6, "g/dL"),
            "creatinine": (0.8, "mg/dL"),
            "glucose": (88, "mg/dL"),
            "crp": (0.6, "mg/L"),
            "lymphocyte_pct": (34, "%"),
            "mcv": (89, "fL"),
            "rdw": (12.4, "%"),
            "alp": (58, "U/L"),
            "wbc": (5.4, "10^9/L"),
        },
    ),
    (
        "SYN-DEMO-002",
        "male",
        "1958-09-30",
        68,
        {
            "albumin": (39, "g/L"),
            "creatinine": (105, "umol/L"),
            "glucose": (6.9, "mmol/L"),
            "crp": (6.5, "mg/L"),
            "lymphocyte_pct": (21, "%"),
            "mcv": (94, "fL"),
            "rdw": (14.9, "%"),
            "alp": (98, "U/L"),
            "wbc": (8.1, "10^9/L"),
        },
    ),
]


def call(method: str, path: str, payload: dict | None = None) -> dict | list:
    req = urllib.request.Request(  # noqa: S310 - fixed local API base
        API + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:  # noqa: S310
        return json.loads(r.read())


def main() -> int:
    if not TOKEN:
        print("API_TOKEN is required", file=sys.stderr)
        return 2
    collected = (date.today() - timedelta(days=3)).isoformat()
    for pseudonym, sex, dob, age, labs in PROFILES:
        p = call(
            "POST", "/api/v1/patients", {"pseudonym": pseudonym, "sex": sex, "birth_date": dob, "is_synthetic": True}
        )
        stored = call(
            "POST",
            f"/api/v1/patients/{p['id']}/labs",
            {
                "collected_on": collected,
                "source": "synthetic",
                "source_detail": "seed_synthetic.py",
                "measurements": [{"biomarker": k, "value": v, "unit": u} for k, (v, u) in labs.items()],
            },
        )
        res = call(
            "POST",
            "/api/v1/bioage/phenoage",
            {
                "chronological_age": age,
                "patient_id": p["id"],
                "lab_result_ids": [lab["id"] for lab in stored],
            },
        )
        print(f"{pseudonym}: patient={p['id']} result={res['result_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
