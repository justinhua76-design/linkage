"""API tests: compute endpoint, RBAC, patient flow, audit, PHI-free logs."""

import copy
import json
import logging
from datetime import date, timedelta

import pytest

from tests.conftest import SI_PROFILE, auth
from tests.reference_impl import reference_phenoage

URL = "/api/v1/bioage/phenoage"


def body(age=50, **overrides):
    b = {"chronological_age": age, "biomarkers": copy.deepcopy(SI_PROFILE)}
    for k, v in overrides.items():
        b["biomarkers"][k] = v
    return b


# ------------------------------------------------------------------ auth
def test_requires_token(client):
    r = client.post(URL, json=body())
    assert r.status_code == 401 and r.json()["code"] == "UNAUTHENTICATED"
    r = client.post(URL, json=body(), headers={"Authorization": "Bearer wrong-token-123456789"})
    assert r.status_code == 401


def test_viewer_cannot_compute(client):
    assert client.post(URL, json=body(), headers=auth("viewer")).status_code == 403


def test_researcher_cannot_create_patient_or_persist(client):
    r = client.post("/api/v1/patients", json={"pseudonym": "SYN-R1", "sex": "female"}, headers=auth("researcher"))
    assert r.status_code == 403
    pid = client.post(
        "/api/v1/patients", json={"pseudonym": "SYN-R2", "sex": "female"}, headers=auth("clinician")
    ).json()["id"]
    r = client.post(URL, json={**body(), "patient_id": pid}, headers=auth("researcher"))
    assert r.status_code == 403


def test_only_admin_reads_audit(client):
    assert client.get("/api/v1/audit-logs", headers=auth("clinician")).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=auth("admin")).status_code == 200


# ------------------------------------------------------------------ compute
def test_compute_ok_matches_reference(client):
    r = client.post(URL, json=body(), headers=auth("researcher"))
    assert r.status_code == 200, r.text
    j = r.json()
    ref, m, _ = reference_phenoage(
        dict(albumin=45, creatinine=80, glucose=5.0, crp=0.1, lymphocyte_pct=30, mcv=90, rdw=13, alp=70, wbc=6, age=50)
    )
    assert abs(j["phenoage"] - float(ref)) < 1e-6
    assert abs(j["mortality_score"] - float(m)) < 1e-9
    assert j["phenoage_rounded"] == round(float(ref), 1)
    assert j["status"] == "ok" and j["result_id"] is None
    # provenance
    assert j["model"]["model_id"] == "levine_phenoage_2018"
    assert j["model"]["model_version"] == "1.0.0"
    assert "10.18632/aging.101414" in j["model"]["algorithm_source"]
    assert len(j["model"]["coefficients_sha256"]) == 64
    assert j["computed_at"]
    crp = next(i for i in j["inputs"] if i["code"] == "crp")
    assert crp["original_unit"] == "mg/L" and crp["canonical_unit"] == "mg/dL"
    assert crp["conversion_factor"] == 0.1
    assert "研究" in j["disclaimer"]


@pytest.mark.parametrize(
    "override,code",
    [
        ({"crp": {"value": 0, "unit": "mg/L"}}, "CRP_ZERO"),
        ({"rdw": {"value": 42, "unit": "fL"}}, "UNIT_NOT_ALLOWED"),
        ({"albumin": {"value": 4.5, "unit": "g/L"}}, "OUT_OF_PLAUSIBLE_RANGE"),
        ({"glucose": {"value": 5.0, "unit": "mmol"}}, "UNIT_UNKNOWN"),
        ({"wbc": {"value": -3, "unit": "10^9/L"}}, "NEGATIVE_VALUE"),
        ({"mcv": {"value": None, "unit": "fL"}}, "MISSING_VALUE"),
    ],
)
def test_invalid_inputs_never_return_an_age(client, override, code):
    r = client.post(URL, json=body(**override), headers=auth("clinician"))
    assert r.status_code == 422
    j = r.json()
    assert j["status"] == "rejected"
    assert code in {e["code"] for e in j["errors"]}
    assert "phenoage" not in j and "phenoage_rounded" not in j


def test_missing_biomarker_key(client):
    b = body()
    del b["biomarkers"]["alp"]
    r = client.post(URL, json=b, headers=auth("clinician"))
    assert r.status_code == 422 and "phenoage" not in r.json()


def test_string_number_rejected_by_schema(client):
    r = client.post(URL, json=body(albumin={"value": "45", "unit": "g/L"}), headers=auth("clinician"))
    assert r.status_code == 422 and r.json()["code"] == "SCHEMA_VALIDATION_FAILED"


def test_nan_rejected(client):
    raw = json.dumps(body()).replace('"value": 45', '"value": NaN')
    r = client.post(URL, content=raw, headers={**auth("clinician"), "Content-Type": "application/json"})
    assert r.status_code == 422
    assert "phenoage" not in r.json()


def test_unknown_fields_rejected(client):
    b = body()
    b["biomarkers"]["crp"]["foo"] = 1
    assert client.post(URL, json=b, headers=auth("clinician")).status_code == 422


def test_crp_below_lod_via_api(client):
    r = client.post(URL, json=body(crp={"below_lod": True, "lod": 0.2, "unit": "mg/L"}), headers=auth("clinician"))
    assert r.status_code == 200
    j = r.json()
    assert any(w["code"] == "CRP_BELOW_LOD_IMPUTED" for w in j["warnings"])
    assert j["lod_policy"] == "lod_div_sqrt2"


def test_age_out_of_range(client):
    r = client.post(URL, json=body(age=150), headers=auth("clinician"))
    assert r.status_code == 422


def test_shape_requires_exactly_one_source(client):
    r = client.post(URL, json={"chronological_age": 50}, headers=auth("clinician"))
    assert r.status_code == 422 and r.json()["code"] == "BAD_REQUEST_SHAPE"


def test_biomarker_catalog(client):
    r = client.get("/api/v1/bioage/biomarkers", headers=auth("viewer"))
    assert r.status_code == 200
    codes = [b["code"] for b in r.json()["biomarkers"]]
    assert len(codes) == 9 and "crp" in codes


# ------------------------------------------------------------------ patient flow
LABS = [
    {"biomarker": "albumin", "value": 4.4, "unit": "g/dL"},
    {"biomarker": "creatinine", "value": 0.9, "unit": "mg/dL"},
    {"biomarker": "glucose", "value": 92, "unit": "mg/dL"},
    {
        "biomarker": "crp",
        "value": 1.5,
        "unit": "mg/L",
        "reference_low": 0,
        "reference_high": 5,
        "reference_unit": "mg/L",
    },
    {"biomarker": "lymphocyte_pct", "value": 31, "unit": "%"},
    {"biomarker": "mcv", "value": 89, "unit": "fL"},
    {"biomarker": "rdw", "value": 12.9, "unit": "%"},
    {"biomarker": "alp", "value": 65, "unit": "U/L"},
    {"biomarker": "wbc", "value": 5.8, "unit": "10^9/L"},
]


def test_full_patient_flow(client):
    h = auth("clinician")
    p = client.post(
        "/api/v1/patients",
        json={"pseudonym": "SYN-0001", "sex": "female", "birth_date": "1975-03-02", "is_synthetic": True},
        headers=h,
    )
    assert p.status_code == 201, p.text
    pid = p.json()["id"]
    assert client.post("/api/v1/patients", json={"pseudonym": "SYN-0001", "sex": "male"}, headers=h).status_code == 409

    collected = (date.today() - timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/v1/patients/{pid}/labs",
        json={"collected_on": collected, "source": "synthetic", "source_detail": "pytest", "measurements": LABS},
        headers=h,
    )
    assert r.status_code == 201, r.text
    labs = r.json()
    assert len(labs) == 9
    crp = next(lab for lab in labs if lab["biomarker"] == "crp")
    assert crp["value_canonical"] == pytest.approx(0.15) and crp["reference_source"] == "lab"
    alb = next(lab for lab in labs if lab["biomarker"] == "albumin")
    assert alb["value_canonical"] == pytest.approx(44.0) and alb["unit_original"] == "g/dL"
    assert alb["reference_source"] == "system_default" and alb["quality_status"] == "valid"

    r = client.post(
        URL,
        json={"chronological_age": 51.5, "patient_id": pid, "lab_result_ids": [lab["id"] for lab in labs]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["result_id"] and res["patient_id"] == pid
    assert set(res["lab_result_ids"]) == {lab["id"] for lab in labs}

    # stored result is reproducible & retrievable
    g = client.get(f"/api/v1/bioage/results/{res['result_id']}", headers=auth("viewer"))
    assert g.status_code == 200
    assert g.json()["phenoage"] == res["phenoage"]
    assert g.json()["model"] == res["model"]

    ov = client.get(f"/api/v1/patients/{pid}/overview", headers=auth("viewer")).json()
    assert len(ov["latest_labs"]) == 9 and len(ov["results"]) == 1

    # audit entries exist and carry no clinical values
    logs = client.get("/api/v1/audit-logs", headers=auth("admin")).json()
    actions = {entry["action"] for entry in logs}
    assert {"patient.create", "lab.create", "bioage.phenoage.compute", "bioage.result.read"} <= actions
    dump = json.dumps(logs)
    assert "SYN-0001" not in dump and "1975-03-02" not in dump and "51.5" not in dump


def test_lab_batch_rejected_atomically(client):
    h = auth("clinician")
    pid = client.post("/api/v1/patients", json={"pseudonym": "SYN-0002", "sex": "male"}, headers=h).json()["id"]
    bad = copy.deepcopy(LABS)
    bad[0] = {"biomarker": "albumin", "value": 44, "unit": "g/dL"}  # 440 g/L -> implausible
    r = client.post(
        f"/api/v1/patients/{pid}/labs", json={"collected_on": date.today().isoformat(), "measurements": bad}, headers=h
    )
    assert r.status_code == 422
    assert client.get(f"/api/v1/patients/{pid}/labs", headers=h).json() == []


def test_lab_ids_from_other_patient_rejected(client):
    h = auth("clinician")
    p1 = client.post("/api/v1/patients", json={"pseudonym": "SYN-A", "sex": "male"}, headers=h).json()["id"]
    p2 = client.post("/api/v1/patients", json={"pseudonym": "SYN-B", "sex": "male"}, headers=h).json()["id"]
    labs = client.post(
        f"/api/v1/patients/{p1}/labs", json={"collected_on": date.today().isoformat(), "measurements": LABS}, headers=h
    ).json()
    r = client.post(
        URL, json={"chronological_age": 50, "patient_id": p2, "lab_result_ids": [lab["id"] for lab in labs]}, headers=h
    )
    assert r.status_code == 404


def test_incomplete_stored_labs_do_not_compute(client):
    h = auth("clinician")
    pid = client.post("/api/v1/patients", json={"pseudonym": "SYN-C", "sex": "male"}, headers=h).json()["id"]
    labs = client.post(
        f"/api/v1/patients/{pid}/labs",
        json={"collected_on": date.today().isoformat(), "measurements": LABS[:8]},
        headers=h,
    ).json()
    r = client.post(
        URL, json={"chronological_age": 50, "patient_id": pid, "lab_result_ids": [lab["id"] for lab in labs]}, headers=h
    )
    assert r.status_code == 422 and "phenoage" not in r.json()


def test_pseudonym_pattern_blocks_free_text(client):
    r = client.post(
        "/api/v1/patients", json={"pseudonym": "张三 110101199001011234", "sex": "male"}, headers=auth("clinician")
    )
    assert r.status_code == 422


# ------------------------------------------------------------------ logging
def test_application_logs_contain_no_patient_data(client, caplog):
    h = auth("clinician")
    caplog.set_level(logging.DEBUG)
    # capture the formatted output of the real handler (with PHI filter)
    root = logging.getLogger()
    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record):
            lines.append(root.handlers[0].format(record))

    cap = Capture()
    for f in root.handlers[0].filters:
        cap.addFilter(f)
    root.addHandler(cap)
    try:
        pid = client.post(
            "/api/v1/patients", json={"pseudonym": "SYN-LOG-77", "sex": "female", "birth_date": "1961-07-19"}, headers=h
        ).json()["id"]
        client.post(
            URL, json={**body(age=63.25, albumin={"value": 41.37, "unit": "g/L"}), "patient_id": pid}, headers=h
        )
        client.post(
            URL, json=body(crp={"value": 0, "unit": "mg/L"}, glucose={"value": 7.77, "unit": "mmol/L"}), headers=h
        )
        # an accidental unsafe log call must also be scrubbed by the filter
        logging.getLogger("app.test").info("oops value=%s", 41.37, extra={"pseudonym": "SYN-LOG-77"})
    finally:
        root.removeHandler(cap)
    text = "\n".join(lines)
    assert lines, "expected access logs"
    for secret in ("SYN-LOG-77", "1961-07-19", "41.37", "63.25", "7.77"):
        assert secret not in text, secret
    assert '"route": "/api/v1/bioage/phenoage"' in text
