"""BHRT engine, report parser and API tests (synthetic data only)."""

import base64
import copy
from datetime import date

import pytest

from app.domain.bhrt.engine import evaluate
from app.domain.bhrt.intake import BhrtIntake
from app.domain.bhrt.report_parser import parse_text
from tests.conftest import auth

TODAY = date(2026, 11, 10)

FEMALE_LABS = [
    {"code": "e2", "value": 15, "unit": "pg/mL"},
    {"code": "fsh", "value": 70, "unit": "mIU/mL"},
    {"code": "total_t", "value": 0.6, "unit": "nmol/L"},
    {"code": "shbg", "value": 60, "unit": "nmol/L"},
    {"code": "tsh", "value": 2.0, "unit": "uIU/mL"},
    {"code": "alt", "value": 20, "unit": "U/L"},
    {"code": "ast", "value": 22, "unit": "U/L"},
    {"code": "creatinine", "value": 60, "unit": "umol/L"},
    {"code": "tc", "value": 5.0, "unit": "mmol/L"},
    {"code": "tg", "value": 1.1, "unit": "mmol/L"},
    {"code": "ldl", "value": 3.0, "unit": "mmol/L"},
    {"code": "hb", "value": 130, "unit": "g/L"},
    {"code": "hct", "value": 40, "unit": "%"},
]

BASE = {
    "client_ref": "SYN-001",
    "sex": "female",
    "age": 53,
    "height_cm": 160,
    "weight_kg": 58,
    "bp_systolic": 120,
    "bp_diastolic": 78,
    "repro_stage": "postmenopause",
    "years_since_fmp": 2,
    "uterus_intact": True,
    #       hot slp dep irr anx fat sex bla dry joi + heart(1)
    "mrs": [3, 1, 2, 1, 1, 1, 1, 0, 0, 1, 1],
    "labs": FEMALE_LABS,
    "breast_imaging": {"performed_on": "2026-09-01", "modality": "ultrasound", "birads": 2},
    "pelvic_us": {"performed_on": "2026-09-01", "endometrial_thickness_mm": 3},
    "evaluation_date": TODAY.isoformat(),
}


def run(**over):
    data = copy.deepcopy(BASE)
    for k, v in over.items():
        data[k] = v
    return evaluate(BhrtIntake.model_validate(data))


def codes(ev):
    return [r.product_code for r in ev.prescription]


# ------------------------------------------------------------------ happy path
def test_early_postmenopause_cream_draft():
    ev = run()
    assert ev.status == "draft", (ev.missing, ev.risks)
    assert ev.stage["code"] == "B"
    assert ev.route["selected"] == "cream"
    assert codes(ev) == ["biest_05", "prog_oral_100"]
    biest = ev.prescription[0]
    assert biest.dose == "1 转" and "E2 0.25 mg" in biest.active_dose
    assert "Topi-Click 30 g × 1" in biest.duration_quantity  # 90 clicks < 120 per container
    assert "100 mg" in ev.endometrial_protection
    assert ev.monitoring and ev.client_instructions


def test_no_uterus_no_protection_and_sleep_gets_oral():
    ev = run(uterus_intact=False, mrs=[3, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0])
    assert ev.status == "draft"
    assert codes(ev) == ["biest_05", "prog_oral_100"]
    assert "睡眠" in ev.prescription[1].purpose
    assert "子宫已切除" in ev.endometrial_protection


def test_fibroids_default_to_vaginal_progesterone_with_pending_spec():
    ev = run(history={"fibroids": True})
    assert "prog_vaginal" in codes(ev)
    assert any("阴道用黄体酮" in p for p in ev.pending)
    assert any(r.code == "FIBROIDS" for r in ev.risks)


def test_cream_progesterone_for_protection_is_documented_deviation():
    ev = run(preferences={"progesterone": "cream"})
    assert "prog_cream_10" in codes(ev)
    assert ev.deviations and "NAMS" in ev.deviations[0]


def test_perimenopause_without_vms_gets_progesterone_only():
    ev = run(
        repro_stage="perimenopause",
        years_since_fmp=None,
        age=46,
        mrs=[0, 0, 3, 1, 1, 2, 1, 0, 0, 0, 0],
        labs=FEMALE_LABS + [{"code": "progesterone", "value": 0.5, "unit": "ng/mL"}],
    )
    assert ev.status == "draft", ev.missing
    assert ev.stage["code"] == "A"
    assert codes(ev) == ["prog_oral_100"]
    assert "14–25" in ev.prescription[0].frequency


def test_late_postmenopause_gsm_only_local_therapy():
    ev = run(age=66, years_since_fmp=15, mrs=[0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 0])
    assert ev.stage["code"] == "C"
    assert codes(ev) == ["estriol_vaginal"]


def test_hsdd_testosterone_only_when_confirmed():
    ev = run(mrs=[3, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0])
    assert "t_cream_f" not in codes(ev)
    ev = run(mrs=[3, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0], hsdd_confirmed=True)
    assert "t_cream_f" in codes(ev)


# ------------------------------------------------------------------ completeness
def test_missing_labs_and_imaging_give_checklist_no_doses():
    ev = run(labs=FEMALE_LABS[:3], breast_imaging=None)
    assert ev.status == "incomplete"
    assert ev.prescription == []
    items = {m.item for m in ev.missing if m.required}
    assert any("BI-RADS" in i for i in items)
    assert any("TSH" in i for i in items)


def test_stale_labs_count_as_missing():
    labs = copy.deepcopy(FEMALE_LABS)
    labs[0]["collected_on"] = "2026-01-01"
    ev = run(labs=labs)
    assert ev.status == "incomplete"
    assert any("超过" in e for e in ev.lab_errors)


def test_unit_conversion_pmol_to_pg():
    labs = copy.deepcopy(FEMALE_LABS)
    labs[0] = {"code": "e2", "value": 100, "unit": "pmol/L"}
    ev = run(labs=labs)
    e2 = next(lab for lab in ev.labs if lab.code == "e2")
    assert e2.value == pytest.approx(27.24)


# ------------------------------------------------------------------ gates
def test_breast_cancer_stops():
    ev = run(history={"breast_cancer": True})
    assert ev.status == "stop" and ev.prescription == []


def test_undiagnosed_bleeding_holds():
    ev = run(abnormal_bleeding="undiagnosed")
    assert ev.status == "hold" and ev.prescription == []
    assert any("异常子宫出血" in r for r in ev.referrals)


def test_birads3_blocks_pellet_but_not_cream():
    ev = run(
        breast_imaging={"birads": 3},
        medications={"stable_on_transdermal": True},
        preferences={"route": "pellet", "pellet_consent_signed": True},
    )
    assert ev.status == "draft"
    assert ev.route["selected"] == "cream"
    assert any("BI-RADS 3" in b for b in ev.route["pellet_blockers"])


def test_pellet_when_all_conditions_met():
    ev = run(
        medications={"stable_on_transdermal": True, "current_hrt": "Bi-Est 0.5% 1转"},
        preferences={"route": "pellet", "pellet_consent_signed": True},
    )
    assert ev.route["selected"] == "pellet", ev.route
    assert "e2_pellet" in codes(ev)


def test_liver_enzymes_hold():
    labs = copy.deepcopy(FEMALE_LABS)
    labs[5] = {"code": "alt", "value": 150, "unit": "U/L"}
    ev = run(labs=labs)
    assert ev.status == "hold"


def test_uncontrolled_bp_holds():
    assert run(bp_systolic=170, bp_diastolic=95).status == "hold"


# ------------------------------------------------------------------ men
MALE = {
    "client_ref": "SYN-M1",
    "sex": "male",
    "age": 52,
    "height_cm": 175,
    "weight_kg": 80,
    "bp_systolic": 125,
    "bp_diastolic": 80,
    "adam": [True, True, False, False, False, False, True, False, False, False],
    "history": {"sleep_apnea": "no"},
    "labs": [
        {"code": "total_t", "value": 200, "unit": "ng/dL"},
        {"code": "hct", "value": 45, "unit": "%"},
        {"code": "hb", "value": 150, "unit": "g/L"},
        {"code": "psa", "value": 1.0, "unit": "ng/mL"},
        {"code": "lh", "value": 3, "unit": "IU/L"},
        {"code": "fsh", "value": 4, "unit": "IU/L"},
        {"code": "e2", "value": 20, "unit": "pg/mL"},
        {"code": "alt", "value": 20, "unit": "U/L"},
        {"code": "ast", "value": 20, "unit": "U/L"},
        {"code": "creatinine", "value": 80, "unit": "umol/L"},
        {"code": "tc", "value": 5, "unit": "mmol/L"},
        {"code": "tg", "value": 1.5, "unit": "mmol/L"},
        {"code": "ldl", "value": 3, "unit": "mmol/L"},
    ],
    "male_total_t_repeat": {"code": "total_t", "value": 7.5, "unit": "nmol/L"},
    "evaluation_date": TODAY.isoformat(),
}


def test_male_hypogonadism_draft():
    ev = evaluate(BhrtIntake.model_validate(MALE))
    assert ev.status == "draft", (ev.missing, ev.risks)
    assert codes(ev) == ["t_cream_m"]


def test_male_high_hct_and_fertility_hold():
    m = copy.deepcopy(MALE)
    m["labs"][1]["value"] = 55
    assert evaluate(BhrtIntake.model_validate(m)).status == "hold"
    m = copy.deepcopy(MALE)
    m["history"]["desires_fertility"] = True
    assert evaluate(BhrtIntake.model_validate(m)).status == "hold"


# ------------------------------------------------------------------ parser
REPORT = """检验项目 结果 单位 参考范围
雌二醇(E2) 18.5 pg/mL
促卵泡生成素 FSH 68.2 mIU/mL
游离睾酮 1.2 pg/mL
总睾酮 0.8 nmol/L 0.29-1.67
促甲状腺激素 TSH 2.1 uIU/mL 0.27-4.2
红细胞压积 0.39
孕酮 <0.2 ng/mL
乳腺超声：BI-RADS 3类
子宫内膜厚约 0.5cm，子宫肌瘤 2.1cm"""


def test_parser_extracts_values_units_and_imaging():
    r = parse_text(REPORT)
    by = {lab.code: lab for lab in r.labs}
    assert by["e2"].value == 18.5 and by["e2"].unit == "pg/mL"
    assert by["fsh"].unit == "IU/L"
    assert by["free_t"].value == 1.2 and by["total_t"].value == 0.8  # longest alias wins
    assert by["tsh"].unit == "mIU/L"
    assert by["hct"].unit == "L/L"
    assert by["progesterone"].below_detection
    assert r.imaging.birads == 3
    assert r.imaging.endometrial_thickness_mm == 5.0
    assert r.imaging.fibroids is True


# ------------------------------------------------------------------ API
def test_api_requires_permission(client):
    assert client.post("/api/v1/bhrt/evaluate", json=BASE, headers=auth("viewer")).status_code == 403
    assert client.post("/api/v1/bhrt/evaluate", json=BASE, headers=auth("researcher")).status_code == 403


def test_api_evaluate_and_parse(client):
    r = client.post("/api/v1/bhrt/evaluate", json=BASE, headers=auth("clinician"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft"
    r = client.post("/api/v1/bhrt/reports/parse", json={"text": REPORT}, headers=auth("clinician"))
    assert r.status_code == 200 and len(r.json()["labs"]) >= 6
    assert client.get("/api/v1/bhrt/catalog", headers=auth("clinician")).status_code == 200


def test_api_rejects_non_pdf(client):
    b64 = base64.b64encode(b"hello world").decode()
    r = client.post("/api/v1/bhrt/reports/parse", json={"pdf_base64": b64}, headers=auth("clinician"))
    assert r.status_code == 422 and r.json()["code"] == "PDF_INVALID"
