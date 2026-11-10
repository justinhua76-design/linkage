"""BHRT decision engine: intake -> evaluation result with prescription draft.

Deterministic and rule-based. Age never maps to a dose: age / reproductive
stage decide eligibility, gating, route and how cautiously to start; dose is
set by symptoms + labs and titrated at follow-up.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from app.domain.bhrt import rules as R
from app.domain.bhrt.intake import BhrtIntake
from app.domain.bhrt.labs import ANALYTES, LabUnitError, to_canonical
from app.domain.bhrt.products import CLICKS_PER_CONTAINER, PRODUCTS

ENGINE_VERSION = "bhrt-0.1.0"

STOP, HOLD, CAUTION, INFO = "STOP", "HOLD", "CAUTION", "INFO"
_LEVEL_ORDER = {STOP: 3, HOLD: 2, CAUTION: 1, INFO: 0}


# ====================================================================== result types
@dataclass
class MissingItem:
    category: str  # basic | stage | symptoms | history | lab | imaging
    item: str
    required: bool
    reason: str


@dataclass
class LabOut:
    code: str
    name_zh: str
    value: float
    unit: str
    collected_on: str | None
    flag: str  # normal | high | low | critical
    note: str = ""


@dataclass
class Risk:
    level: str
    code: str
    title: str
    detail: str
    action: str
    scope: str = "all"  # all | pellet | testosterone


@dataclass
class RxItem:
    product_code: str
    product_name: str
    strength: str
    dose: str
    active_dose: str
    route_site: str
    frequency: str
    duration_quantity: str
    purpose: str
    pending_spec: bool = False


@dataclass
class FollowUp:
    when: str
    label: str
    items: list[str]


@dataclass
class Evaluation:
    status: str  # incomplete | stop | hold | draft
    status_label: str
    engine_version: str
    client_ref: str
    sex: str
    age: int
    bmi: float | None
    bp: str | None
    stage: dict
    missing: list[MissingItem]
    labs: list[LabOut]
    lab_errors: list[str]
    risks: list[Risk]
    gate: str  # PROCEED | CAUTION | HOLD | STOP
    symptoms: dict
    route: dict
    prescription: list[RxItem]
    endometrial_protection: str
    client_instructions: list[str]
    referrals: list[str]
    monitoring: list[FollowUp]
    expected_outcomes: list[dict]
    deviations: list[str]
    assumptions: list[str]
    pending: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


# ====================================================================== helpers
@dataclass
class _Ctx:
    intake: BhrtIntake
    today: date
    labs: dict[str, float] = field(default_factory=dict)
    lab_out: list[LabOut] = field(default_factory=list)
    lab_errors: list[str] = field(default_factory=list)
    missing: list[MissingItem] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    referrals: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def risk(self, level: str, code: str, title: str, detail: str, action: str, scope: str = "all") -> None:
        if not any(r.code == code for r in self.risks):
            self.risks.append(Risk(level, code, title, detail, action, scope))

    def need(self, category: str, item: str, required: bool, reason: str) -> None:
        if not any(m.item == item for m in self.missing):
            self.missing.append(MissingItem(category, item, required, reason))

    def refer(self, text: str) -> None:
        if text not in self.referrals:
            self.referrals.append(text)

    def lab(self, code: str) -> float | None:
        return self.labs.get(code)


def _fmt(v: float) -> str:
    return f"{v:g}" if abs(v) >= 0.01 else f"{v:.3g}"


def _bmi(i: BhrtIntake) -> float | None:
    if i.height_cm and i.weight_kg:
        return round(i.weight_kg / (i.height_cm / 100) ** 2, 1)
    return None


def _mrs(i: BhrtIntake, idx: int) -> int:
    return i.mrs[idx] if i.mrs else 0


# ====================================================================== step 1: labs + completeness
def _load_labs(c: _Ctx) -> None:
    i = c.intake
    for lv in i.labs:
        a = ANALYTES.get(lv.code)
        if a is None:
            c.lab_errors.append(f"未知检测项目代码 '{lv.code}'，已忽略")
            continue
        try:
            v = to_canonical(lv.code, lv.value, lv.unit)
        except LabUnitError as e:
            c.lab_errors.append(e.message)
            continue
        if lv.collected_on and (c.today - lv.collected_on).days > R.LAB_MAX_AGE_DAYS:
            c.lab_errors.append(
                f"{a.name_zh}: 采样日期 {lv.collected_on} 超过 {R.LAB_MAX_AGE_DAYS} 天，视为缺项，请复查"
            )
            continue
        if lv.code in c.labs:
            c.lab_errors.append(f"{a.name_zh} 重复录入，使用第一条")
            continue
        c.labs[lv.code] = v
        c.lab_out.append(
            LabOut(
                lv.code,
                a.name_zh,
                round(v, 3),
                a.canonical_unit,
                lv.collected_on.isoformat() if lv.collected_on else None,
                "normal",
            )
        )
    if i.labs and any(lv.collected_on is None for lv in i.labs):
        c.assumptions.append("部分检测未填写采样日期，已假设在有效期内")


def _check_completeness(c: _Ctx) -> None:
    i = c.intake
    if i.height_cm is None or i.weight_kg is None:
        c.need("basic", "身高 / 体重（BMI）", True, "BMI 影响途径选择与血栓风险评估")
    if i.bp_systolic is None or i.bp_diastolic is None:
        c.need("basic", "血压", True, "未控制的高血压需先稳定")

    if i.sex == "female":
        if i.repro_stage == "unknown":
            c.need(
                "stage", "生殖分期（规律月经 / 围绝经 / 绝经 / 手术绝经或 POI）", True, "分期决定适应证、途径与起始强度"
            )
        if i.repro_stage == "postmenopause" and i.years_since_fmp is None:
            c.need("stage", "末次月经距今年数", True, "区分绝经早期（<10 年）与晚期")
        if i.uterus_intact is None:
            c.need("stage", "子宫是否保留", True, "决定是否需要子宫内膜保护")
        if i.mrs is None:
            c.need("symptoms", "MRS 更年期评分量表（11 项）", True, "症状决定用药方向与剂量")
        required: list[str] = list(R.FEMALE_REQUIRED_LABS)
        if i.repro_stage in ("cycling", "perimenopause"):
            required += R.FEMALE_CYCLING_REQUIRED
        if i.hsdd_confirmed:
            required += R.FEMALE_HSDD_REQUIRED
        recommended: tuple[str, ...] = R.FEMALE_RECOMMENDED_LABS
        # breast imaging
        bi = i.breast_imaging
        if bi is None or bi.birads is None:
            c.need("imaging", "乳腺钼靶 / 乳腺超声（BI-RADS 分级）", True, "排除乳腺病变后方可使用全身雌激素")
        elif bi.performed_on and (c.today - bi.performed_on).days > R.IMAGING_MAX_AGE_DAYS:
            c.need("imaging", "乳腺影像（已超过 12 个月，需复查）", True, "影像需在指南间隔内")
        # pelvic ultrasound
        pu = i.pelvic_us
        tvus_required = bool(i.uterus_intact) and (
            i.abnormal_bleeding != "none" or i.preferences.route == "pellet" or i.history.fibroids
        )
        if i.uterus_intact and (pu is None or pu.endometrial_thickness_mm is None):
            c.need(
                "imaging",
                "经阴道超声（子宫内膜厚度）",
                tvus_required,
                "有出血史 / 肌瘤 / 计划 Pellet 时必须；其余情况作为基线建议",
            )
        elif pu and pu.performed_on and (c.today - pu.performed_on).days > R.IMAGING_MAX_AGE_DAYS:
            c.need("imaging", "经阴道超声（已超过 12 个月）", tvus_required, "需在有效期内")
        if _mrs(i, R.MRS_JOINT) >= R.MRS_SIGNIFICANT and i.dexa_t_score is None:
            c.need("imaging", "骨密度 DEXA", False, "关节/骨骼症状，评估骨量")
    else:
        if i.adam is None:
            c.need("symptoms", "ADAM 男性雄激素缺乏问卷（10 项）", True, "症状是诊断性腺功能减退的前提")
        required = list(R.MALE_REQUIRED_LABS)
        recommended = R.MALE_RECOMMENDED_LABS
        if i.male_total_t_repeat is None:
            c.need("lab", "第二次晨起（7–11 点）总睾酮", True, "需两次晨起低睾酮方可诊断")
        if i.history.sleep_apnea == "unknown":
            c.need("history", "睡眠呼吸暂停筛查（STOP-BANG）", True, "未治疗的重度 OSA 为暂缓条件")

    # symptom-driven extra work-up (fatigue / brain fog)
    if i.sex == "female" and _mrs(i, R.MRS_FATIGUE) >= R.MRS_SIGNIFICANT:
        recommended = tuple(dict.fromkeys((*recommended, "ft4", "ferritin", "b12", "vitd")))

    for code in required:
        if code not in c.labs:
            c.need("lab", ANALYTES[code].name_zh, True, "基线必查")
    for code in recommended:
        if code not in c.labs:
            c.need("lab", ANALYTES[code].name_zh, False, "建议补充")


# ====================================================================== step 2: risk analysis
def _flag(c: _Ctx, code: str, flag: str, note: str) -> None:
    for lo in c.lab_out:
        if lo.code == code:
            lo.flag, lo.note = flag, note


def _analyse_labs(c: _Ctx) -> None:
    i = c.intake
    sex = i.sex
    alt, ast = c.lab("alt"), c.lab("ast")
    for code, v, uln in (("alt", alt, R.ALT_ULN), ("ast", ast, R.AST_ULN)):
        if v is None:
            continue
        if v > uln * R.LIVER_HOLD_MULTIPLE:
            _flag(c, code, "critical", f">{R.LIVER_HOLD_MULTIPLE:g}×ULN")
            c.risk(
                HOLD,
                "LIVER_ENZYMES",
                "肝酶显著升高",
                f"{code.upper()} {_fmt(v)} U/L，超过正常上限 3 倍",
                "肝病科评估；明确后优先非口服途径",
            )
            c.refer("肝病科：肝酶显著升高")
        elif v > uln:
            _flag(c, code, "high", "高于正常上限")
            c.risk(
                CAUTION, "LIVER_MILD", "肝酶轻度升高", f"{code.upper()} {_fmt(v)} U/L", "优先经皮途径，4–8 周复查肝功能"
            )

    cr = c.lab("creatinine")
    if cr is not None and cr > R.CREATININE_ULN[sex]:
        _flag(c, "creatinine", "high", "高于正常上限")
        c.risk(CAUTION, "RENAL", "肌酐升高", f"肌酐 {_fmt(cr)} µmol/L", "评估肾功能（eGFR），必要时肾内科会诊")

    ldl, tg = c.lab("ldl"), c.lab("tg")
    if ldl is not None and ldl >= R.LDL_VERY_HIGH:
        _flag(c, "ldl", "critical", "显著升高")
        c.risk(
            CAUTION,
            "LDL_VERY_HIGH",
            "LDL-C 显著升高",
            f"LDL-C {_fmt(ldl)} mmol/L",
            "心血管风险评估（ASCVD ± CAC），考虑降脂治疗；经皮途径优先",
        )
    elif ldl is not None and ldl >= R.LDL_HIGH:
        _flag(c, "ldl", "high", "升高")
        c.risk(INFO, "LDL_HIGH", "LDL-C 升高", f"LDL-C {_fmt(ldl)} mmol/L", "生活方式干预，定期复查血脂")
    if tg is not None and tg >= R.TG_VERY_HIGH:
        _flag(c, "tg", "critical", "显著升高")
        c.risk(
            CAUTION,
            "TG_VERY_HIGH",
            "甘油三酯显著升高",
            f"TG {_fmt(tg)} mmol/L",
            "避免口服雌激素（本方案仅用经皮雌激素）；胰腺炎风险评估",
        )
    elif tg is not None and tg >= R.TG_HIGH:
        _flag(c, "tg", "high", "升高")

    glu, a1c = c.lab("glucose"), c.lab("hba1c")
    if (glu is not None and glu >= R.GLUCOSE_DM) or (a1c is not None and a1c >= R.HBA1C_DM):
        if glu is not None and glu >= R.GLUCOSE_DM:
            _flag(c, "glucose", "high", "达糖尿病切点")
        if a1c is not None and a1c >= R.HBA1C_DM:
            _flag(c, "hba1c", "high", "达糖尿病切点")
        c.risk(
            CAUTION,
            "DIABETES",
            "血糖达糖尿病诊断切点",
            "空腹血糖或 HbA1c 升高",
            "内分泌科确诊与管理；纳入心血管风险评估",
        )
    elif glu is not None and glu >= R.GLUCOSE_IFG:
        _flag(c, "glucose", "high", "空腹血糖受损")

    tsh = c.lab("tsh")
    if tsh is not None and not (R.TSH_LOW <= tsh <= R.TSH_HIGH):
        _flag(c, "tsh", "high" if tsh > R.TSH_HIGH else "low", "超出参考范围")
        c.risk(
            CAUTION,
            "THYROID",
            "甲状腺功能异常",
            f"TSH {_fmt(tsh)} mIU/L",
            "先评估/纠正甲状腺功能：潮热、心悸、疲劳、情绪症状可能源于甲状腺",
        )
        c.refer("内分泌科：TSH 异常")

    hb, hct = c.lab("hb"), c.lab("hct")
    if sex == "female":
        if hb is not None and hb < R.HB_LOW_FEMALE:
            _flag(c, "hb", "low", "贫血")
            c.risk(CAUTION, "ANEMIA", "贫血", f"Hb {_fmt(hb)} g/L", "查铁蛋白/失血原因（含异常子宫出血）")
        if hct is not None and hct > R.HCT_HIGH_FEMALE:
            _flag(c, "hct", "high", "升高")
            c.risk(
                CAUTION, "HCT_F", "红细胞压积偏高", f"Hct {_fmt(hct)}%", "睾酮治疗前需复查并明确原因", "testosterone"
            )
        tt = c.lab("total_t")
        if tt is not None and tt > R.FEMALE_TOTAL_T_ULN:
            _flag(c, "total_t", "high", "高于女性生理上限")
            c.risk(
                CAUTION,
                "T_HIGH_F",
                "女性总睾酮已偏高",
                f"TT {_fmt(tt)} nmol/L",
                "不加用睾酮；评估多囊卵巢/肾上腺来源",
                "testosterone",
            )
        fsh = c.lab("fsh")
        if fsh is not None and fsh >= R.FSH_POSTMENOPAUSAL:
            _flag(c, "fsh", "high", "符合绝经过渡晚期/绝经后")
            if i.repro_stage == "cycling":
                c.risk(
                    INFO, "FSH_STAGE", "FSH 与分期不一致", f"FSH {_fmt(fsh)} IU/L 但记录为规律月经", "核对月经史与分期"
                )
    else:
        if hct is not None and hct >= R.HCT_HOLD_MALE:
            _flag(c, "hct", "critical", "≥54%")
            c.risk(HOLD, "HCT_M", "红细胞压积 ≥54%", f"Hct {_fmt(hct)}%", "暂停/不起始睾酮；明确红细胞增多原因")
            c.refer("血液科：红细胞增多")
        elif hct is not None and hct >= R.HCT_CAUTION_MALE:
            _flag(c, "hct", "high", "偏高")
            c.risk(CAUTION, "HCT_M_BORDER", "红细胞压积偏高", f"Hct {_fmt(hct)}%", "起始剂量保守，4–6 周复查 Hct")
        psa = c.lab("psa")
        if psa is not None and psa >= R.PSA_HOLD:
            _flag(c, "psa", "high", "≥4 ng/mL")
            c.risk(HOLD, "PSA", "PSA 升高", f"PSA {_fmt(psa)} ng/mL", "泌尿外科评估后再考虑睾酮")
            c.refer("泌尿外科：PSA 升高")

    for code, thr, title in (
        ("vitd", R.VITD_DEFICIENT, "维生素 D 缺乏"),
        ("ferritin", R.FERRITIN_LOW, "铁蛋白偏低"),
        ("b12", R.B12_LOW, "维生素 B12 偏低"),
    ):
        v = c.lab(code)
        if v is not None and v < thr:
            _flag(c, code, "low", "偏低")
            c.risk(
                INFO,
                f"LOW_{code.upper()}",
                title,
                f"{ANALYTES[code].name_zh} {_fmt(v)}",
                "补充并复查；疲劳/脑雾可能与此相关",
            )


def _analyse_history(c: _Ctx, bmi: float | None) -> None:
    i, h, f, m = c.intake, c.intake.history, c.intake.family, c.intake.medications
    if i.bp_systolic and i.bp_diastolic:
        if i.bp_systolic >= R.BP_UNCONTROLLED[0] or i.bp_diastolic >= R.BP_UNCONTROLLED[1]:
            c.risk(HOLD, "BP_UNCONTROLLED", "血压未控制", f"{i.bp_systolic}/{i.bp_diastolic} mmHg", "先控制血压再开始")
            c.refer("心内科：血压控制")
        elif i.bp_systolic >= R.BP_ELEVATED[0] or i.bp_diastolic >= R.BP_ELEVATED[1]:
            c.risk(CAUTION, "BP_ELEVATED", "血压偏高", f"{i.bp_systolic}/{i.bp_diastolic} mmHg", "经皮途径；监测血压")
    if bmi is not None and bmi >= R.BMI_OBESE:
        c.risk(CAUTION, "OBESITY", "肥胖（BMI ≥30）", f"BMI {bmi}", "血栓风险增加：经皮途径优先")
    if i.smoker:
        c.risk(CAUTION, "SMOKER", "吸烟", "心血管与血栓风险增加", "经皮途径优先；建议戒烟")

    if i.sex == "female":
        if h.breast_cancer or m.tamoxifen_or_ai:
            c.risk(STOP, "BREAST_CA", "乳腺癌病史 / 正在内分泌治疗", "全身雌激素禁忌", "肿瘤科转诊")
            c.refer("肿瘤科：乳腺癌病史")
        if h.endometrial_cancer:
            c.risk(STOP, "ENDO_CA", "子宫内膜癌病史", "全身雌激素禁忌", "妇科肿瘤科转诊")
            c.refer("妇科肿瘤科：子宫内膜癌病史")
        if h.ovarian_cancer:
            c.risk(HOLD, "OVARIAN_CA", "卵巢癌病史", "需肿瘤科意见", "肿瘤科评估后再决定")
            c.refer("肿瘤科：卵巢癌病史")
        if i.abnormal_bleeding == "undiagnosed":
            c.risk(
                HOLD,
                "AUB",
                "未明确诊断的异常子宫出血",
                "出血需先排除病理",
                "经阴道超声 ± 宫腔镜/内膜活检（第 8 节流程）",
            )
            c.refer("妇科：异常子宫出血评估（TVUS ± 宫腔镜/活检）")
        bi = i.breast_imaging
        if bi and bi.birads is not None:
            if bi.birads in (4, 5, 6):
                c.risk(STOP, "BIRADS_45", f"乳腺 BI-RADS {bi.birads}", "可疑恶性", "乳腺外科转诊")
                c.refer("乳腺外科：BI-RADS 4–6")
            elif bi.birads == 3:
                c.risk(
                    HOLD,
                    "BIRADS_3",
                    "乳腺 BI-RADS 3",
                    "可能良性，需短期复查",
                    "短期复查/活检明确前不用 Pellet；乳膏需医师接受并密切随访",
                    "pellet",
                )
                c.risk(CAUTION, "BIRADS_3_CREAM", "乳腺 BI-RADS 3（乳膏）", "需医师确认可接受", "3–6 个月复查乳腺影像")
            elif bi.birads == 0:
                c.risk(HOLD, "BIRADS_0", "乳腺 BI-RADS 0", "影像评估不完整", "补充影像检查")
        pu = i.pelvic_us
        if (
            pu
            and pu.endometrial_thickness_mm is not None
            and i.uterus_intact
            and i.repro_stage in ("postmenopause", "surgical_or_poi")
        ):
            t = pu.endometrial_thickness_mm
            if i.abnormal_bleeding != "none" and t > R.ENDOMETRIUM_POSTMENO_BLEEDING_MM:
                c.risk(
                    HOLD,
                    "ENDO_THICK_BLEED",
                    "绝经后出血且内膜增厚",
                    f"内膜 {_fmt(t)} mm",
                    "内膜活检 / 宫腔镜（第 8 节流程）",
                )
                c.refer("妇科：内膜活检")
            elif t > R.ENDOMETRIUM_POSTMENO_ASYMPTOMATIC_MM:
                c.risk(HOLD, "ENDO_THICK", "绝经后内膜明显增厚", f"内膜 {_fmt(t)} mm", "妇科评估后再开始")
                c.refer("妇科：内膜增厚评估")
        if h.fibroids or (pu and pu.fibroids):
            c.risk(
                CAUTION, "FIBROIDS", "子宫肌瘤", "雌激素可能促进肌瘤", "强化子宫内膜保护（阴道黄体酮优先）+ TVUS 监测"
            )
        if h.endometriosis:
            c.risk(
                CAUTION,
                "ENDOMETRIOSIS",
                "子宫内膜异位症",
                "雌激素可能激活残留病灶",
                "即使已切除子宫也考虑联用孕激素，由医师决定",
            )
        if h.migraine_with_aura:
            c.risk(CAUTION, "MIGRAINE_AURA", "先兆偏头痛", "血药浓度波动诱发风险", "仅用乳膏（浓度平稳）；避免 Pellet")
            c.risk(HOLD, "MIGRAINE_AURA_PELLET", "先兆偏头痛（Pellet）", "Pellet 早期峰值", "不使用 Pellet", "pellet")
        if h.gallbladder_disease:
            c.risk(CAUTION, "GALLBLADDER", "胆囊疾病", "口服雌激素加重风险", "经皮途径")
        if f.brca_carrier or f.breast_cancer_early_onset or f.breast_cancer_first_degree:
            c.risk(
                CAUTION,
                "FAMILY_BREAST",
                "乳腺癌家族史 / BRCA",
                "乳腺风险升高",
                "遗传咨询；最低有效剂量；每年乳腺影像（必要时 MRI）",
            )
    else:
        if h.prostate_cancer:
            c.risk(STOP, "PROSTATE_CA", "前列腺癌病史", "睾酮治疗禁忌", "泌尿肿瘤科转诊")
            c.refer("泌尿肿瘤科：前列腺癌病史")
        if h.abnormal_dre:
            c.risk(HOLD, "DRE", "直肠指检异常", "需排除前列腺病变", "泌尿外科评估")
            c.refer("泌尿外科：直肠指检异常")
        if h.sleep_apnea == "untreated":
            c.risk(HOLD, "OSA", "未治疗的睡眠呼吸暂停", "睾酮可加重 OSA", "先行 CPAP 等治疗")
            c.refer("睡眠医学科：OSA 治疗")
        if h.desires_fertility:
            c.risk(
                HOLD, "FERTILITY", "有生育计划", "外源性睾酮抑制精子生成", "生殖男科评估（如 hCG/克罗米芬等替代方案）"
            )
            c.refer("生殖男科：保留生育力方案")

    # thrombosis / CV
    if h.vte_active:
        c.risk(HOLD, "VTE_ACTIVE", "活动性血栓", "需抗凝治疗与专科意见", "血液科/心内科评估")
        c.refer("血液科：活动性 VTE")
    elif h.vte or h.thrombophilia or f.thrombophilia:
        if h.vte_cleared_by_specialist:
            c.risk(CAUTION, "VTE_CLEARED", "血栓史（已获专科许可）", "仅限经皮途径", "不使用 Pellet；最低有效剂量")
        else:
            c.risk(HOLD, "VTE_RISK", "血栓史 / 易栓症", "高血栓风险", "血液科/心内科评估；许可后仅用经皮途径")
            c.refer("血液科：血栓风险评估")
        c.risk(HOLD, "VTE_PELLET", "血栓风险（Pellet）", "Pellet 不可随时停药", "不使用 Pellet", "pellet")
    if h.stroke_mi:
        c.risk(HOLD, "CVD", "卒中 / 心梗病史", "心血管高危", "心内科/神经内科评估")
        c.refer("心内科：心血管事件史")
    if m.anticoagulant:
        c.risk(CAUTION, "ANTICOAG", "正在抗凝", "提示血栓病史；植入出血风险", "核实抗凝原因；不使用 Pellet")
        c.risk(HOLD, "ANTICOAG_PELLET", "抗凝（Pellet）", "植入出血风险", "不使用 Pellet", "pellet")
    if h.liver_disease_active or h.autoimmune_liver_antibody_positive:
        if h.liver_cleared_by_specialist:
            c.risk(CAUTION, "LIVER_CLEARED", "肝病（已获专科许可）", "避免口服首过", "非口服途径优先")
        else:
            c.risk(HOLD, "LIVER", "活动性肝病 / 自身免疫肝抗体阳性", "需肝病科意见", "肝病科评估（AMA-M2、gp210 等）")
            c.refer("肝病科：肝病/自身免疫肝抗体")


# ====================================================================== step 3: stage
def _stage(c: _Ctx) -> dict:
    i = c.intake
    if i.sex == "male":
        return {"code": "M", "label": "男性性腺功能减退评估", "implication": "症状 + 两次晨起低总睾酮方可诊断"}
    s = i.repro_stage
    if s in ("cycling", "perimenopause"):
        return {
            "code": "A",
            "label": "围绝经期（仍有月经）",
            "implication": "孕激素优先；持续血管舒缩症状才加低剂量雌激素；暂不推荐 Pellet；BHRT 不能避孕",
        }
    if s == "surgical_or_poi" and i.age < 45:
        return {
            "code": "D",
            "label": "手术绝经 / 早发性卵巢功能不全（<45 岁）",
            "implication": "强烈建议雌激素至少至平均绝经年龄；无子宫则无需内膜保护",
        }
    ysf = i.years_since_fmp
    if s in ("postmenopause", "surgical_or_poi"):
        if ysf is not None and ysf < 10 and i.age < 60:
            return {
                "code": "B",
                "label": "绝经早期（<10 年且 <60 岁）",
                "implication": "获益/风险最有利窗口；乳膏或 Pellet",
            }
        if ysf is None and s == "postmenopause":
            return {"code": "?", "label": "绝经后（年数待补）", "implication": "需补充末次月经时间"}
        return {
            "code": "C",
            "label": "绝经晚期（≥10 年或 ≥60 岁）",
            "implication": "正式心血管风险评估；最低起始；乳膏优先，Pellet 非一线；仅 GSM 用局部治疗",
        }
    return {"code": "?", "label": "分期待补", "implication": "需补充生殖分期"}


# ====================================================================== step 4: symptoms
def _symptoms(c: _Ctx) -> dict:
    i = c.intake
    if i.sex == "male":
        a = i.adam or []
        positive = bool(a) and (a[0] or a[6] or sum(a) >= 3)
        return {
            "scale": "ADAM",
            "positive": positive,
            "yes_count": sum(a),
            "items": [R.ADAM_ITEMS[k] for k, v in enumerate(a) if v],
            "map": [],
        }
    mrs = i.mrs or [0] * 11
    total = sum(mrs)
    severity = next(lbl for hi, lbl in R.MRS_SEVERITY if total <= hi)
    sig = R.MRS_SIGNIFICANT
    mapping: list[dict] = []

    def add(symptom: str, lever: str, check: str) -> None:
        mapping.append({"symptom": symptom, "lever": lever, "check_first": check})

    if mrs[R.MRS_HOT_FLASH] >= sig:
        add("潮热 / 盗汗", "雌二醇", "甲状腺、药物因素")
    if mrs[R.MRS_SLEEP] >= sig:
        add("睡眠障碍", "黄体酮（睡前，口服效果更佳）", "睡眠呼吸暂停、抑郁")
    if max(mrs[R.MRS_ANXIETY], mrs[R.MRS_IRRITABLE], mrs[R.MRS_DEPRESS]) >= sig:
        add("焦虑 / 易激惹 / 情绪低落", "黄体酮（睡前）；伴潮热时雌二醇", "抑郁筛查（PHQ-9）")
    if mrs[R.MRS_SEX] >= sig:
        add(
            "性欲低下",
            "睾酮（女性唯一循证适应证：HSDD）" if i.hsdd_confirmed else "待确认 HSDD 后考虑睾酮",
            "伴侣关系、SSRI、GSM 疼痛",
        )
    if max(mrs[R.MRS_DRYNESS], mrs[R.MRS_BLADDER]) >= sig:
        add("阴道干涩 / 性交痛 / 反复尿感", "局部阴道雌激素（雌三醇）", "尿常规、尿培养")
    if mrs[R.MRS_BLADDER] >= sig:
        add("尿频", "未证实前不归因于激素", "尿常规/培养、残余尿、血糖")
    if mrs[R.MRS_FATIGUE] >= sig:
        add("疲劳 / 脑雾", "多因素", "TSH、铁蛋白、B12、维生素 D、血常规、抑郁筛查")
    if mrs[R.MRS_JOINT] >= sig:
        add("关节痛 / 骨量", "雌二醇", "DEXA、维生素 D、炎症指标")
    if mrs[R.MRS_HEART] >= sig:
        add("心悸", "先排查", "心电图、甲状腺功能")
    return {
        "scale": "MRS",
        "total": total,
        "severity": severity,
        "somatic": mrs[0] + mrs[1] + mrs[2] + mrs[10],
        "psychological": mrs[3] + mrs[4] + mrs[5] + mrs[6],
        "urogenital": mrs[7] + mrs[8] + mrs[9],
        "top_complaints": i.top_complaints
        or [R.MRS_ITEMS[k] for k in sorted(range(11), key=lambda k: -mrs[k])[:3] if mrs[k] > 0],
        "map": mapping,
    }


# ====================================================================== step 5-6: route + doses
def _containers(clicks_per_day: float, days: int) -> int:
    return max(1, math.ceil(clicks_per_day * days / CLICKS_PER_CONTAINER))


def _cream(code: str, clicks: float, frequency: str, days: int, site: str, purpose: str) -> RxItem:
    p = PRODUCTS[code]
    active = f"{_fmt(p.mg_per_unit * clicks)} mg" if p.mg_per_unit else "待确认"
    if code.startswith("biest") and p.mg_per_unit:
        e2 = 0.125 if code == "biest_025" else 0.25
        active = f"Bi-Est {_fmt(p.mg_per_unit * clicks)} mg（E2 {_fmt(e2 * clicks)} mg）"
    return RxItem(
        code,
        p.name_zh,
        p.strength,
        f"{_fmt(clicks)} 转",
        active,
        site,
        frequency,
        f"{p.package} × {_containers(clicks, days)}（约 {days} 天用量）",
        purpose,
    )


def _pending(c: _Ctx, code: str, dose: str, site: str, freq: str, purpose: str) -> RxItem:
    p = PRODUCTS[code]
    c.pending.append(f"{p.name_zh}：{p.note}")
    return RxItem(code, p.name_zh, p.strength, dose, "待确认", site, freq, "规格确认后计算", purpose, pending_spec=True)


def _blocked(c: _Ctx, scope: str) -> list[Risk]:
    return [r for r in c.risks if r.scope == scope and _LEVEL_ORDER[r.level] >= _LEVEL_ORDER[HOLD]]


def _female_plan(c: _Ctx, stage: str, sym: dict) -> tuple[dict, list[RxItem], str]:
    i = c.intake
    mrs = i.mrs or [0] * 11
    sig = R.MRS_SIGNIFICANT
    days = 90
    vms = mrs[R.MRS_HOT_FLASH] >= sig
    sleep_primary = mrs[R.MRS_SLEEP] >= 3 or any("睡" in t for t in i.top_complaints)
    sleep_any = mrs[R.MRS_SLEEP] >= sig
    mood = max(mrs[R.MRS_ANXIETY], mrs[R.MRS_IRRITABLE], mrs[R.MRS_DEPRESS]) >= sig
    gsm = max(mrs[R.MRS_DRYNESS], mrs[R.MRS_BLADDER]) >= sig
    joint = mrs[R.MRS_JOINT] >= sig
    low_bone = i.dexa_t_score is not None and i.dexa_t_score <= -1.0

    # --- systemic estrogen indication
    if stage == "D":
        need_e = True
    elif stage == "A":
        need_e = vms
    elif stage == "B":
        need_e = vms or joint or low_bone or (mood and vms)
    else:  # C
        need_e = vms

    # --- testosterone indication (HSDD only)
    t_blocked = _blocked(c, "testosterone")
    need_t = i.hsdd_confirmed and mrs[R.MRS_SEX] >= sig and not t_blocked and c.lab("total_t") is not None

    # --- route
    pellet_blockers: list[str] = [f"{r.title}" for r in _blocked(c, "pellet")]
    if stage in ("A", "C"):
        pellet_blockers.append("围绝经期/绝经晚期：Pellet 非一线")
    if any(r.level == CAUTION and r.code in ("VTE_CLEARED", "MIGRAINE_AURA", "ANTICOAG") for r in c.risks):
        pellet_blockers.append("血栓/偏头痛/抗凝相关风险")
    if not i.medications.stable_on_transdermal:
        pellet_blockers.append("尚无乳膏稳定疗效记录（建议先乳膏滴定）")
    if not i.preferences.pellet_consent_signed:
        pellet_blockers.append("未签署 Pellet 知情同意（早期峰值、不可取出、雄激素不可逆效应）")
    if i.uterus_intact and (i.pelvic_us is None or i.pelvic_us.endometrial_thickness_mm is None):
        pellet_blockers.append("缺少基线经阴道超声")
    wants_pellet = i.preferences.route == "pellet" or (
        i.preferences.route == "no_preference" and i.preferences.poor_daily_adherence
    )
    use_pellet = wants_pellet and not pellet_blockers and (need_e or need_t)
    reasons: list[str] = []
    if use_pellet:
        reasons.append("无闸门限制，第 10 节 Pellet 前清单通过，已有乳膏稳定疗效，客户偏好免每日涂抹")
    else:
        reasons.append("乳膏优先：可当日停用、便于滴定")
        if wants_pellet:
            reasons.append("客户希望 Pellet，但以下条件未满足：" + "；".join(pellet_blockers))
    route = {
        "selected": "pellet" if use_pellet else "cream",
        "selected_label": "Pellet 皮下植入" if use_pellet else "经皮乳膏",
        "reasons": reasons,
        "pellet_blockers": pellet_blockers,
    }

    rx: list[RxItem] = []
    site = "前臂内侧 / 大腿内侧，轮换部位"
    if need_e:
        if use_pellet:
            cautious = any(r.level == CAUTION for r in c.risks) or not i.medications.current_hrt
            mg = 6 if cautious else 12.5
            rx.append(
                RxItem(
                    "e2_pellet",
                    PRODUCTS["e2_pellet"].name_zh,
                    "单粒",
                    f"{_fmt(mg)} mg",
                    f"E2 {_fmt(mg)} mg",
                    "臀上外侧皮下",
                    "单次植入",
                    "下次植入前查谷值（E2 >150 pg/mL 则推迟）",
                    "血管舒缩症状 / 雌激素缺乏",
                )
            )
        else:
            code, clicks = {"A": ("biest_025", 1), "B": ("biest_05", 1), "C": ("biest_025", 1), "D": ("biest_05", 1)}[
                stage
            ]
            rx.append(_cream(code, clicks, "每日早晨 1 次", days, site, "血管舒缩症状 / 雌激素缺乏"))
        c.assumptions.append("乳膏 1 转 = 250 mg（Topi-Click 30 g ≈120 转），使用前需按分装器核实")

    # --- progesterone
    protection_needed = bool(i.uterus_intact) and need_e
    pref = i.preferences.progesterone
    fibroids = any(r.code == "FIBROIDS" for r in c.risks)
    endo = ""
    if protection_needed:
        if pref == "cream":
            rx.append(_cream("prog_cream_10", 4, "每晚睡前，连续", days, site, "子宫内膜保护（偏离默认）"))
            c.deviations.append(
                "按医师选择以黄体酮乳膏作内膜保护：经皮黄体酮不被视为可靠内膜保护（NAMS 2022）。"
                "须基线 TVUS，6 个月复查，此后每年；任何出血按第 8 节评估。"
            )
            endo = "黄体酮乳膏（偏离默认，需 TVUS 监测：基线、6 个月、每年）"
        elif pref == "vaginal" or (pref == "auto" and fibroids and not sleep_primary):
            rx.append(
                _pending(
                    c,
                    "prog_vaginal",
                    "按产品规格（内膜保护等效剂量）",
                    "阴道给药",
                    "每晚睡前，连续或每月 12–14 天",
                    "子宫内膜保护",
                )
            )
            endo = "阴道黄体酮" + ("（子宫肌瘤：强化保护 + TVUS 监测）" if fibroids else "")
        else:
            if stage == "A":
                rx.append(
                    RxItem(
                        "prog_oral_100",
                        PRODUCTS["prog_oral_100"].name_zh,
                        "100 mg",
                        "2 粒",
                        "200 mg",
                        "口服",
                        "每晚睡前，月经周期第 14–25 天",
                        f"{12 * 3} 粒（3 个周期）",
                        "子宫内膜保护" + ("+ 睡眠" if sleep_any else ""),
                    )
                )
                endo = "口服微粒化黄体酮 200 mg 睡前，周期第 14–25 天"
            else:
                rx.append(
                    RxItem(
                        "prog_oral_100",
                        PRODUCTS["prog_oral_100"].name_zh,
                        "100 mg",
                        "1 粒",
                        "100 mg",
                        "口服",
                        "每晚睡前，连续",
                        f"{days} 粒",
                        "子宫内膜保护" + ("+ 睡眠" if sleep_any else ""),
                    )
                )
                endo = "口服微粒化黄体酮 100 mg 每晚连续"
            if pref == "auto" and not sleep_primary:
                c.assumptions.append("内膜保护默认口服微粒化黄体酮；亦可改为阴道黄体酮（贵方确认规格后）")
    else:
        endo = "子宫已切除，无需内膜保护" if i.uterus_intact is False else "未使用全身雌激素，无需内膜保护"
        if stage == "A" or sleep_any or mood:
            cyc = stage == "A"
            freq = "每晚睡前，月经周期第 14–25 天" if cyc else "每晚睡前"
            n_days = 36 if cyc else days
            if (sleep_primary or (sleep_any and pref == "oral")) and pref != "cream":
                mg = 200 if cyc else 100
                rx.append(
                    RxItem(
                        "prog_oral_100",
                        PRODUCTS["prog_oral_100"].name_zh,
                        "100 mg",
                        f"{mg // 100} 粒",
                        f"{mg} mg",
                        "口服",
                        freq,
                        f"{n_days * mg // 100} 粒",
                        "睡眠（口服对睡眠效果更佳）",
                    )
                )
            else:
                rx.append(
                    _cream("prog_cream_10", 2, freq, n_days, site, "围绝经期孕激素支持" if cyc else "情绪 / 睡眠支持")
                )
                c.assumptions.append("经皮黄体酮血药浓度不能可靠反映剂量，按症状滴定（2–4 转）")

    # --- testosterone
    if need_t:
        if use_pellet:
            bmi = _bmi(i)
            mg = 50 if (bmi is None or bmi < 25) else 75
            rx.append(
                RxItem(
                    "t_pellet",
                    PRODUCTS["t_pellet"].name_zh,
                    "单粒",
                    f"{mg} mg",
                    f"T {mg} mg",
                    "臀上外侧皮下",
                    "单次植入",
                    "约 4 周查总睾酮；谷值超女性上限则推迟再植入",
                    "性欲低下（HSDD）",
                )
            )
        else:
            rx.append(
                _pending(c, "t_cream_f", "目标约 0.3 mg/日（按浓度换算转数）", site, "每日 1 次", "性欲低下（HSDD）")
            )
    elif mrs[R.MRS_SEX] >= sig and not i.hsdd_confirmed:
        c.pending.append("性欲低下：需医师确认 HSDD（排除关系、SSRI、GSM 疼痛）后方可考虑睾酮")

    # --- local GSM therapy
    if gsm:
        rx.append(
            _pending(
                c, "estriol_vaginal", "按产品规格", "阴道给药", "起始每晚 2 周，后每周 2 次", "泌尿生殖综合征（GSM）"
            )
        )
    if stage == "C" and not need_e and gsm:
        c.assumptions.append("绝经晚期仅 GSM 症状：仅用局部阴道治疗，不用全身雌激素")
    return route, rx, endo


def _male_plan(c: _Ctx, sym: dict) -> tuple[dict, list[RxItem], str]:
    i = c.intake
    t1 = c.lab("total_t")
    t2 = None
    if i.male_total_t_repeat:
        try:
            t2 = to_canonical("total_t", i.male_total_t_repeat.value, i.male_total_t_repeat.unit)
        except LabUnitError as e:
            c.lab_errors.append("第二次总睾酮：" + e.message)
    low = [t for t in (t1, t2) if t is not None and t < R.MALE_T_LOW]
    borderline = [t for t in (t1, t2) if t is not None and R.MALE_T_LOW <= t < R.MALE_T_BORDERLINE]
    if t1 is not None and t2 is not None:
        if len(low) < 2 and not borderline:
            c.risk(
                HOLD,
                "T_NOT_LOW",
                "未达性腺功能减退诊断",
                "两次晨起总睾酮未均低于 9.2 nmol/L",
                "不起始睾酮；查找症状其他原因",
            )
        elif len(low) < 2:
            c.risk(CAUTION, "T_BORDERLINE", "总睾酮处于临界", "9.2–12 nmol/L", "结合游离睾酮 / SHBG 判断")
            if c.lab("free_t") is None and c.lab("shbg") is None:
                c.need("lab", "游离睾酮或 SHBG", True, "总睾酮临界时必需")
    if not sym.get("positive") and i.adam is not None:
        c.risk(HOLD, "ADAM_NEG", "ADAM 问卷阴性", "症状不支持", "不起始睾酮")

    blockers = [r.title for r in _blocked(c, "pellet")]
    if not i.medications.stable_on_transdermal:
        blockers.append("尚无乳膏稳定疗效记录")
    if not i.preferences.pellet_consent_signed:
        blockers.append("未签署 Pellet 知情同意")
    use_pellet = i.preferences.route == "pellet" and not blockers
    route = {
        "selected": "pellet" if use_pellet else "cream",
        "selected_label": "Pellet 皮下植入" if use_pellet else "经皮乳膏",
        "reasons": ["Pellet 条件满足"] if use_pellet else ["乳膏优先，便于滴定与停药"],
        "pellet_blockers": blockers,
    }
    rx: list[RxItem] = []
    if use_pellet:
        rx.append(
            RxItem(
                "t_pellet",
                PRODUCTS["t_pellet"].name_zh,
                "75 mg/粒",
                "医师确定（标签范围 150–450 mg）",
                "待医师填写",
                "臀上外侧皮下",
                "每 3–6 个月",
                "4–6 周查峰值；再植入前查谷值 + PSA",
                "男性性腺功能减退",
            )
        )
        c.pending.append("男性睾酮 Pellet 起始剂量需医师按标签范围（150–450 mg）确定；超出为超说明书使用")
    else:
        rx.append(
            _pending(c, "t_cream_m", "按贵方男性方案", "肩部 / 上臂 / 腹部，轮换", "每日早晨 1 次", "男性性腺功能减退")
        )
    return route, rx, "不适用（男性）"


# ====================================================================== step 7-8: monitoring + outcomes
def _monitoring(c: _Ctx, start: date, pellet: bool) -> list[FollowUp]:
    i = c.intake

    def d(days: int) -> str:
        return (start + timedelta(days=days)).isoformat()

    male = i.sex == "male"
    if male:
        peak = ["总睾酮", "雌二醇", "红细胞压积"]
        trough = ["总睾酮（谷值）", "PSA", "红细胞压积"]
    else:
        peak = ["雌二醇（标记 >200 pg/mL）", "总睾酮", "红细胞压积"]
        trough = ["雌二醇谷值（>150 pg/mL 推迟植入）", "总睾酮谷值"]
    plan = [FollowUp(start.isoformat(), "开始治疗", ["基线检测与影像已存档"])]
    if pellet:
        plan += [
            FollowUp(d(14), "2 周", ["植入部位检查", "耐受性"]),
            FollowUp(d(28), "4 周（峰值）", peak),
            FollowUp(d(49), "6–8 周", ["MRS / 症状评分" if not male else "ADAM / 症状"]),
            FollowUp(d(84), "10–14 周（谷值）", trough + ["决定是否再植入及剂量"]),
        ]
    else:
        plan += [
            FollowUp(d(14), "2 周电话随访", ["耐受性", "有无阴道出血"] if not male else ["耐受性", "皮肤反应"]),
            FollowUp(
                d(49),
                "6–8 周",
                ["MRS 复评", "症状持续则查 E2 后再滴定（每次 ±1 转）"]
                if not male
                else ["ADAM 复评", "总睾酮", "红细胞压积"],
            ),
            FollowUp(d(90), "3 个月", ["复评并稳定剂量"]),
        ]
    plan.append(
        FollowUp(
            d(182),
            "6 个月",
            ["性激素、血常规、血压、体重"]
            + (["TVUS（如使用乳膏黄体酮或肌瘤）"] if (not male and i.uterus_intact) else []),
        )
    )
    plan.append(
        FollowUp(
            d(365), "每年", (["PSA", "红细胞压积", "血脂"] if male else ["乳腺影像", "TVUS（按需）", "血脂", "血常规"])
        )
    )
    return plan


def _outcomes(c: _Ctx, rx: list[RxItem], sym: dict) -> list[dict]:
    codes = {r.product_code for r in rx}
    out = []
    if codes & {"prog_oral_100", "prog_cream_10", "prog_cream_5", "prog_vaginal"}:
        out.append({"domain": "睡眠", "onset": "1–2 周", "track": "睡眠日记"})
    if codes & {"biest_025", "biest_05", "e2_pellet"}:
        out.append({"domain": "潮热", "onset": "2–4 周", "track": "频率/严重度记录、MRS"})
        out.append({"domain": "情绪", "onset": "4–8 周", "track": "MRS 心理子量表"})
        out.append({"domain": "骨骼", "onset": "12 个月以上", "track": "DEXA"})
    if codes & {"t_cream_f", "t_pellet", "t_cream_m"}:
        out.append({"domain": "性欲", "onset": "6–12 周", "track": "性功能评分"})
    if "estriol_vaginal" in codes:
        out.append({"domain": "阴道症状", "onset": "8–12 周", "track": "症状评分"})
    return out


CLIENT_INSTRUCTIONS = [
    "涂抹乳膏前后洗手；部位轮换；涂抹处数小时内避免与儿童、宠物皮肤接触",
    "每日记录症状日记（潮热次数、睡眠、情绪、出血）",
    "请勿自行加量或停药，调整需经医生评估",
    "出现以下情况立即联系医生：任何阴道出血、单侧腿肿痛、胸痛气短、剧烈头痛或视物异常、乳房新发肿块、声音变粗",
]
CLIENT_INSTRUCTIONS_MALE = [
    "涂抹乳膏前后洗手；涂抹处穿衣覆盖，避免与女性、儿童皮肤接触",
    "请勿自行加量或停药，调整需经医生评估",
    "出现以下情况立即联系医生：单侧腿肿痛、胸痛气短、排尿困难、乳房增大或疼痛、明显打鼾/憋醒",
]


# ====================================================================== entry point
def evaluate(intake: BhrtIntake, today: date | None = None) -> Evaluation:
    today = intake.evaluation_date or today or date.today()
    c = _Ctx(intake=intake, today=today)
    bmi = _bmi(intake)
    _load_labs(c)
    _check_completeness(c)
    _analyse_labs(c)
    _analyse_history(c, bmi)
    stage = _stage(c)
    sym = _symptoms(c)

    route: dict = {"selected": None, "selected_label": "—", "reasons": [], "pellet_blockers": []}
    rx: list[RxItem] = []
    endo = ""

    if intake.sex == "male":
        # male diagnosis checks add risks; run before gating
        route, rx, endo = _male_plan(c, sym)

    general = [r for r in c.risks if r.scope == "all"]
    worst = max((_LEVEL_ORDER[r.level] for r in general), default=0)
    gate = {3: "STOP", 2: "HOLD", 1: "CAUTION", 0: "PROCEED"}[worst]
    required_missing = [m for m in c.missing if m.required]

    if gate == "STOP":
        status, label = "stop", "禁忌：不出具处方"
    elif required_missing:
        status, label = "incomplete", "评估待补：资料不全，暂不出具剂量"
    elif gate == "HOLD":
        status, label = "hold", "暂缓处方：需先完成转诊/检查"
    else:
        status, label = "draft", "处方草案：待执业医师审核签字"

    if status != "draft":
        rx, route, endo = [], {"selected": None, "selected_label": "—", "reasons": [], "pellet_blockers": []}, ""
        c.pending = [p for p in c.pending if "规格" not in p and "Pellet" not in p]
    elif intake.sex == "female":
        if stage["code"] == "?":  # unreachable when completeness passes, kept defensive
            status, label = "incomplete", "评估待补：分期不明确"
        else:
            route, rx, endo = _female_plan(c, stage["code"], sym)
            if not rx:
                c.pending.append("当前症状未达用药指征；建议生活方式干预并 3 个月后复评")

    start = intake.start_date or today
    monitoring = _monitoring(c, start, route.get("selected") == "pellet") if status == "draft" else []
    return Evaluation(
        status=status,
        status_label=label,
        engine_version=ENGINE_VERSION,
        client_ref=intake.client_ref,
        sex=intake.sex,
        age=intake.age,
        bmi=bmi,
        bp=f"{intake.bp_systolic}/{intake.bp_diastolic}" if intake.bp_systolic and intake.bp_diastolic else None,
        stage=stage,
        missing=c.missing,
        labs=c.lab_out,
        lab_errors=c.lab_errors,
        risks=sorted(c.risks, key=lambda r: -_LEVEL_ORDER[r.level]),
        gate=gate,
        symptoms=sym,
        route=route,
        prescription=rx,
        endometrial_protection=endo,
        client_instructions=(CLIENT_INSTRUCTIONS_MALE if intake.sex == "male" else CLIENT_INSTRUCTIONS)
        if status == "draft"
        else [],
        referrals=c.referrals,
        monitoring=monitoring,
        expected_outcomes=_outcomes(c, rx, sym) if status == "draft" else [],
        deviations=c.deviations,
        assumptions=list(dict.fromkeys(c.assumptions)),
        pending=list(dict.fromkeys(c.pending)),
    )
