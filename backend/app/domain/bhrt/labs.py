"""Lab analytes: names, report aliases, units and conversions.

Covers every item of the DKi BHRT clinical panel (see panel.py). Analytes the
engine reasons about have strict units with conversion factors; the remaining
panel items accept any unit (``units=None``) and are recorded as reported.
Qualitative items (e.g. HBsAg) use value 1 = 阳性, 0 = 阴性.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.units import _canonicalise


class LabUnitError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Analyte:
    code: str
    name_zh: str
    canonical_unit: str
    # normalised unit -> factor (canonical = value * factor); None = any unit, no conversion
    units: dict[str, float] | None
    # spellings found in Chinese / English lab reports (matched case-insensitively)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    group: str = "other"
    qualitative: bool = False

    @property
    def unit_options(self) -> list[str]:
        return list(self.units) if self.units else [self.canonical_unit]


# Unit spellings -> normalised token
_UNIT_ALIASES: dict[str, str] = {
    "pg/ml": "pg/mL",
    "ng/l": "pg/mL",
    "pmol/l": "pmol/L",
    "ng/ml": "ng/mL",
    "ug/l": "ng/mL",
    "nmol/l": "nmol/L",
    "ng/dl": "ng/dL",
    "ug/dl": "ug/dL",
    "umol/l": "umol/L",
    "mmol/l": "mmol/L",
    "mg/dl": "mg/dL",
    "mg/l": "mg/L",
    "iu/l": "IU/L",
    "miu/ml": "IU/L",
    "mu/ml": "IU/L",
    "u/l": "U/L",
    "u/ml": "U/mL",
    "iu/ml": "IU/mL",
    "miu/l": "mIU/L",
    "uiu/ml": "mIU/L",
    "mu/l": "mIU/L",
    "g/l": "g/L",
    "g/dl": "g/dL",
    "%": "%",
    "l/l": "L/L",
    "fl": "fL",
    "pg": "pg",
    "10^9/l": "10^9/L",
    "x10^9/l": "10^9/L",
    "10*9/l": "10^9/L",
    "10^12/l": "10^12/L",
    "x10^12/l": "10^12/L",
    "10*12/l": "10^12/L",
}


def normalise_lab_unit(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    key = _canonicalise(str(raw))
    return _UNIT_ALIASES.get(key)


def _a(code, name, unit, units, aliases, group, qualitative=False) -> Analyte:  # noqa: ANN001
    return Analyte(code, name, unit, units, tuple(aliases), group, qualitative)


_FREE = None  # any unit accepted

ANALYTES: dict[str, Analyte] = {
    a.code: a
    for a in [
        # ---------------------------------------------------------------- 血脂
        _a(
            "tg",
            "甘油三酯 (TG)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.01129},
            ("甘油三酯", "三酰甘油", "tg", "trig"),
            "lipid",
        ),
        _a(
            "tc",
            "总胆固醇 (TC)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("总胆固醇", "胆固醇", "tc", "chol"),
            "lipid",
        ),
        _a(
            "hdl",
            "高密度脂蛋白胆固醇 (HDL-C)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("高密度脂蛋白胆固醇", "高密度脂蛋白", "hdl-c", "hdl"),
            "lipid",
        ),
        _a(
            "ldl",
            "低密度脂蛋白胆固醇 (LDL-C)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("低密度脂蛋白胆固醇", "低密度脂蛋白", "ldl-c", "ldl"),
            "lipid",
        ),
        _a(
            "apoa1",
            "载脂蛋白A1 (ApoA1)",
            "g/L",
            {"g/L": 1.0, "mg/dL": 0.01},
            ("载脂蛋白a1", "载脂蛋白ai", "载脂蛋白a-i", "apoa1", "apoai", "apo-a1"),
            "lipid",
        ),
        _a("apob", "载脂蛋白B (ApoB)", "g/L", {"g/L": 1.0, "mg/dL": 0.01}, ("载脂蛋白b", "apob", "apo-b"), "lipid"),
        # ---------------------------------------------------------------- 血糖
        _a(
            "glucose",
            "空腹血糖 (GLU)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.0555},
            ("空腹血糖", "空腹葡萄糖", "葡萄糖", "glucose", "glu"),
            "glucose",
        ),
        _a(
            "insulin",
            "胰岛素 (INS)",
            "mIU/L",
            {"mIU/L": 1.0, "pmol/L": 0.144},
            ("空腹胰岛素", "胰岛素", "insulin", "ins"),
            "glucose",
        ),
        _a("hba1c", "糖化血红蛋白 (HbA1c)", "%", {"%": 1.0}, ("糖化血红蛋白", "hba1c"), "glucose"),
        # ---------------------------------------------------------------- 肾功能
        _a(
            "creatinine",
            "肌酐 (Cr)",
            "umol/L",
            {"umol/L": 1.0, "mg/dL": 88.4},
            ("肌酐", "creatinine", "crea", "cr"),
            "renal",
        ),
        _a("uric_acid", "尿酸 (UA)", "umol/L", _FREE, ("尿酸", "uric acid", "ua"), "renal"),
        _a("urea", "尿素氮 (Urea)", "mmol/L", _FREE, ("尿素氮", "尿素", "urea", "bun"), "renal"),
        # ---------------------------------------------------------------- 肝功能
        _a("dbil", "直接胆红素 (D-BIL)", "umol/L", _FREE, ("直接胆红素", "结合胆红素", "d-bil", "dbil"), "liver"),
        _a("ibil", "间接胆红素 (I-BIL)", "umol/L", _FREE, ("间接胆红素", "非结合胆红素", "i-bil", "ibil"), "liver"),
        _a("tbil", "总胆红素 (T-BIL)", "umol/L", _FREE, ("总胆红素", "t-bil", "tbil"), "liver"),
        _a(
            "alt",
            "丙氨酸氨基转移酶 (ALT)",
            "U/L",
            {"U/L": 1.0, "IU/L": 1.0},
            ("丙氨酸氨基转移酶", "谷丙转氨酶", "alt", "gpt"),
            "liver",
        ),
        _a(
            "ast",
            "天门冬氨酸氨基转移酶 (AST)",
            "U/L",
            {"U/L": 1.0, "IU/L": 1.0},
            ("天门冬氨酸氨基转移酶", "天冬氨酸氨基转移酶", "谷草转氨酶", "ast", "got"),
            "liver",
        ),
        _a("alp", "碱性磷酸酶 (ALP)", "U/L", _FREE, ("碱性磷酸酶", "alp", "akp"), "liver"),
        _a("ast_alt", "AST/ALT", "ratio", _FREE, ("ast/alt", "谷草/谷丙"), "liver"),
        _a(
            "ggt",
            "γ-谷氨酰转肽酶 (GGT)",
            "U/L",
            _FREE,
            ("谷氨酰转肽酶", "谷氨酰转移酶", "γ-gt", "y-gt", "r-gt", "ggt"),
            "liver",
        ),
        _a("tp", "总蛋白 (TP)", "g/L", _FREE, ("总蛋白", "tp"), "liver"),
        _a("alb", "白蛋白 (ALB)", "g/L", _FREE, ("白蛋白", "alb"), "liver"),
        _a("ag_ratio", "白球比 (A/G)", "ratio", _FREE, ("白蛋白/球蛋白", "白球比", "a/g"), "liver"),
        _a("glb", "球蛋白 (GLB)", "g/L", _FREE, ("球蛋白", "glb"), "liver"),
        # ---------------------------------------------------------------- 乙肝（定性：1=阳性 0=阴性）
        _a(
            "hbsag",
            "乙肝表面抗原 (HBsAg)",
            "定性",
            _FREE,
            ("乙型肝炎病毒表面抗原", "乙肝表面抗原", "hbsag"),
            "hbv",
            True,
        ),
        _a(
            "hbsab",
            "乙肝表面抗体 (HBsAb)",
            "定性",
            _FREE,
            ("乙型肝炎病毒表面抗体", "乙肝表面抗体", "hbsab", "抗-hbs"),
            "hbv",
            True,
        ),
        _a("hbeag", "乙肝e抗原 (HBeAg)", "定性", _FREE, ("乙型肝炎病毒e抗原", "乙肝e抗原", "hbeag"), "hbv", True),
        _a(
            "hbeab",
            "乙肝e抗体 (HBeAb)",
            "定性",
            _FREE,
            ("乙型肝炎病毒e抗体", "乙肝e抗体", "hbeab", "抗-hbe"),
            "hbv",
            True,
        ),
        _a(
            "hbcab",
            "乙肝核心抗体IgG (HBcAb)",
            "定性",
            _FREE,
            ("乙型肝炎病毒核心抗体", "乙肝核心抗体", "hbcab", "hbc-igg", "bhc-tgg", "抗-hbc"),
            "hbv",
            True,
        ),
        # ---------------------------------------------------------------- 免疫三项
        _a("igm", "免疫球蛋白M (IgM)", "g/L", _FREE, ("免疫球蛋白m", "免疫球蛋白 m", "igm"), "immune"),
        _a("iga", "免疫球蛋白A (IgA)", "g/L", _FREE, ("免疫球蛋白a", "免疫球蛋白 a", "iga"), "immune"),
        _a("igg", "免疫球蛋白G (IgG)", "g/L", _FREE, ("免疫球蛋白g", "免疫球蛋白 g", "igg"), "immune"),
        # ---------------------------------------------------------------- 甲状腺八项
        _a(
            "ft3",
            "游离三碘甲状腺原氨酸 (FT3)",
            "pmol/L",
            _FREE,
            ("游离三碘甲状腺原氨酸", "游离三碘甲状原氨酸", "游离t3", "ft3"),
            "thyroid",
        ),
        _a(
            "ft4",
            "游离甲状腺素 (FT4)",
            "pmol/L",
            {"pmol/L": 1.0, "ng/dL": 12.87},
            ("游离甲状腺素", "游离t4", "ft4"),
            "thyroid",
        ),
        _a(
            "t3",
            "三碘甲状腺原氨酸 (T3)",
            "nmol/L",
            _FREE,
            ("三碘甲状腺原氨酸", "三碘甲状原氨酸", "总t3", "tt3", "t3"),
            "thyroid",
        ),
        _a("t4", "甲状腺素 (T4)", "nmol/L", _FREE, ("甲状腺素", "总t4", "tt4", "t4"), "thyroid"),
        _a("tsh", "促甲状腺激素 (TSH)", "mIU/L", {"mIU/L": 1.0}, ("促甲状腺激素", "促甲状腺素", "tsh"), "thyroid"),
        _a(
            "tgab",
            "甲状腺球蛋白抗体 (TgAb)",
            "IU/mL",
            _FREE,
            ("甲状腺球蛋白抗体", "tgab", "tg-ab", "tga", "yga"),
            "thyroid",
        ),
        _a("tmab", "甲状腺微粒体抗体 (TMAb)", "IU/mL", _FREE, ("甲状腺微粒体抗体", "tmab", "tma"), "thyroid"),
        _a(
            "tpoab",
            "甲状腺过氧化物酶抗体 (TPOAb)",
            "IU/mL",
            _FREE,
            ("甲状腺过氧化物酶抗体", "tpoab", "tpo-ab", "tpoa", "atpo"),
            "thyroid",
        ),
        # ---------------------------------------------------------------- 血常规
        _a("wbc", "白细胞数 (WBC)", "10^9/L", _FREE, ("白细胞计数", "白细胞数", "白细胞", "wbc"), "cbc"),
        _a(
            "neu_pct",
            "中性粒细胞百分比 (NEU%)",
            "%",
            _FREE,
            ("中性粒细胞百分比", "中性粒细胞比率", "neu%", "neut%"),
            "cbc",
        ),
        _a(
            "neu_abs",
            "中性粒细胞绝对数 (NEU#)",
            "10^9/L",
            _FREE,
            ("中性粒细胞绝对", "中性粒细胞计数", "neu#", "neut#"),
            "cbc",
        ),
        _a(
            "ly_pct",
            "淋巴细胞百分比 (LY%)",
            "%",
            _FREE,
            ("淋巴细胞百分比", "淋巴细胞比率", "ly%", "lym%", "lymph%"),
            "cbc",
        ),
        _a(
            "ly_abs",
            "淋巴细胞绝对数 (LY#)",
            "10^9/L",
            _FREE,
            ("淋巴细胞绝对", "淋巴细胞计数", "ly#", "lym#", "lymph#"),
            "cbc",
        ),
        _a(
            "eos_pct",
            "嗜酸性粒细胞百分比 (EOS%)",
            "%",
            _FREE,
            ("嗜酸性粒细胞百分比", "嗜酸性粒细胞比率", "eos%"),
            "cbc",
        ),
        _a(
            "eos_abs",
            "嗜酸性粒细胞绝对值 (EOS#)",
            "10^9/L",
            _FREE,
            ("嗜酸性粒细胞绝对", "嗜酸性粒细胞计数", "eos#"),
            "cbc",
        ),
        _a(
            "bas_pct",
            "嗜碱性粒细胞百分比 (BAS%)",
            "%",
            _FREE,
            ("嗜碱性粒细胞百分比", "嗜碱性粒细胞比率", "bas%", "baso%"),
            "cbc",
        ),
        _a(
            "bas_abs",
            "嗜碱性粒细胞绝对值 (BAS#)",
            "10^9/L",
            _FREE,
            ("嗜碱性粒细胞绝对", "嗜碱性粒细胞计数", "bas#", "baso#"),
            "cbc",
        ),
        _a("mon_pct", "单核细胞百分比 (MON%)", "%", _FREE, ("单核细胞百分比", "单核细胞比率", "mon%", "mono%"), "cbc"),
        _a(
            "mon_abs",
            "单核细胞绝对值 (MON#)",
            "10^9/L",
            _FREE,
            ("单核细胞绝对", "单核细胞计数", "mon#", "mono#"),
            "cbc",
        ),
        _a("rbc", "红细胞 (RBC)", "10^12/L", _FREE, ("红细胞计数", "红细胞数", "rbc"), "cbc"),
        _a("hb", "血红蛋白 (HGB)", "g/L", {"g/L": 1.0, "g/dL": 10.0}, ("血红蛋白", "hgb", "hb"), "cbc"),
        _a(
            "hct",
            "红细胞压积 (HCT)",
            "%",
            {"%": 1.0, "L/L": 100.0},
            ("红细胞压积", "红细胞比容", "红细胞比积", "hct"),
            "cbc",
        ),
        _a("mcv", "平均红细胞体积 (MCV)", "fL", _FREE, ("平均红细胞体积", "mcv"), "cbc"),
        _a("mchc", "平均红细胞血红蛋白浓度 (MCHC)", "g/L", _FREE, ("平均红细胞血红蛋白浓度", "mchc"), "cbc"),
        _a(
            "mch",
            "平均红细胞血红蛋白含量 (MCH)",
            "pg",
            _FREE,
            ("平均红细胞血红蛋白含量", "平均红细胞血红蛋白量", "mch"),
            "cbc",
        ),
        _a(
            "rdw_cv",
            "红细胞分布宽度变异系数 (RDW-CV)",
            "%",
            _FREE,
            ("红细胞分布宽度变异系数", "rdw-cv", "rdwcv"),
            "cbc",
        ),
        _a(
            "rdw_sd",
            "红细胞分布宽度标准差 (RDW-SD)",
            "fL",
            _FREE,
            ("红细胞分布宽度标准差", "红细胞分布宽度(sd)", "rdw-sd", "rdwsd"),
            "cbc",
        ),
        _a("plt", "血小板计数 (PLT)", "10^9/L", _FREE, ("血小板计数", "血小板数", "plt"), "cbc"),
        _a("pdw", "血小板分布宽度 (PDW)", "fL", _FREE, ("血小板分布宽度", "pdw"), "cbc"),
        _a("mpv", "血小板平均体积 (MPV)", "fL", _FREE, ("血小板平均体积", "平均血小板体积", "mpv"), "cbc"),
        _a("pct", "血小板比积 (PCT)", "%", _FREE, ("血小板比积", "血小板压积", "pct"), "cbc"),
        _a("p_lcr", "大血小板比率 (P-LCR)", "%", _FREE, ("大血小板比率", "p-lcr", "plcr"), "cbc"),
        _a("p_lcc", "大血小板数目 (P-LCC)", "10^9/L", _FREE, ("大血小板数目", "大血小板计数", "p-lcc", "plcc"), "cbc"),
        # ---------------------------------------------------------------- 肿瘤标记物
        _a("ferritin", "铁蛋白 (Fer)", "ng/mL", {"ng/mL": 1.0}, ("铁蛋白", "ferritin", "ferr", "fer"), "tumor"),
        _a("afp", "甲胎蛋白 (AFP)", "ng/mL", {"ng/mL": 1.0, "IU/mL": 1.21}, ("甲胎蛋白", "afp"), "tumor"),
        _a("cea", "癌胚抗原 (CEA)", "ng/mL", {"ng/mL": 1.0}, ("癌胚抗原", "cea"), "tumor"),
        _a(
            "ca199",
            "糖类抗原 CA19-9",
            "U/mL",
            {"U/mL": 1.0},
            ("糖类抗原19-9", "糖类抗原ca199", "ca19-9", "ca199"),
            "tumor",
        ),
        _a("ca125", "癌抗原 CA125", "U/mL", {"U/mL": 1.0}, ("癌抗原125", "糖类抗原125", "ca125", "ca-125"), "tumor"),
        _a(
            "ca153",
            "肿瘤抗原 CA15-3",
            "U/mL",
            {"U/mL": 1.0},
            ("癌抗原15-3", "糖类抗原15-3", "肿瘤抗原ca153", "ca15-3", "ca153"),
            "tumor",
        ),
        _a("tnfa", "肿瘤坏死因子 (TNF-α)", "pg/mL", _FREE, ("肿瘤坏死因子", "tnf-α", "tnf-a", "tnfα", "tnf"), "tumor"),
        _a(
            "psa",
            "总前列腺特异性抗原 (TPSA)",
            "ng/mL",
            {"ng/mL": 1.0},
            ("总前列腺特异性抗原", "前列腺特异性抗原", "tpsa", "t-psa", "psa"),
            "tumor",
        ),
        _a(
            "fpsa",
            "游离前列腺特异性抗原 (FPSA)",
            "ng/mL",
            {"ng/mL": 1.0},
            ("游离前列腺特异性抗原", "fpsa", "f-psa"),
            "tumor",
        ),
        # ---------------------------------------------------------------- 电解质（仅中文别名，避免与单位冲突）
        _a("k", "钾 (K)", "mmol/L", _FREE, ("钾",), "electrolyte"),
        _a("na", "钠 (Na)", "mmol/L", _FREE, ("钠",), "electrolyte"),
        _a("cl", "氯 (Cl)", "mmol/L", _FREE, ("氯",), "electrolyte"),
        _a("mg", "镁 (Mg)", "mmol/L", _FREE, ("镁",), "electrolyte"),
        _a("ca", "钙 (Ca)", "mmol/L", _FREE, ("钙",), "electrolyte"),
        _a("phos", "磷 (P)", "mmol/L", _FREE, ("无机磷", "磷"), "electrolyte"),
        # ---------------------------------------------------------------- 性激素
        _a(
            "fsh",
            "促卵泡生成素 (FSH)",
            "IU/L",
            {"IU/L": 1.0},
            ("促卵泡生成素", "促卵泡激素", "卵泡刺激素", "卵泡生成素", "fsh"),
            "hormone",
        ),
        _a(
            "lh",
            "促黄体生成素 (LH)",
            "IU/L",
            {"IU/L": 1.0},
            ("促黄体生成素", "黄体生成素", "促黄体激素", "lh"),
            "hormone",
        ),
        _a(
            "prl",
            "催乳素 (PRL)",
            "ng/mL",
            {"ng/mL": 1.0, "mIU/L": 0.0472},
            ("催泌乳素", "催乳素", "泌乳素", "prl"),
            "hormone",
        ),
        _a(
            "total_t",
            "睾酮 (TES)",
            "nmol/L",
            {"nmol/L": 1.0, "ng/dL": 0.03467, "ng/mL": 3.467},
            ("总睾酮", "睾酮", "total testosterone", "testosterone", "tes", "testo", "tt"),
            "hormone",
        ),
        _a("e2", "雌二醇 (E2)", "pg/mL", {"pg/mL": 1.0, "pmol/L": 0.2724}, ("雌二醇", "estradiol", "e2"), "hormone"),
        _a(
            "progesterone",
            "孕酮 (P)",
            "ng/mL",
            {"ng/mL": 1.0, "nmol/L": 0.3145},
            ("孕酮", "黄体酮", "progesterone", "prog"),
            "hormone",
        ),
        _a("amh", "抗缪勒管激素 (AMH)", "ng/mL", _FREE, ("抗缪勒管激素", "抗苗勒管激素", "amh"), "hormone"),
        # ---------------------------------------------------------------- 其它激素
        _a(
            "dheas",
            "硫酸脱氢表雄酮 (DHEA-S)",
            "ug/dL",
            {"ug/dL": 1.0, "umol/L": 36.81},
            ("硫酸脱氢表雄酮", "脱氢表雄酮硫酸酯", "dhea-s", "dheas", "dhea-so4"),
            "other_hormone",
        ),
        _a("dhea", "脱氢表雄酮 (DHEA)", "ng/mL", _FREE, ("脱氢表雄酮", "dhea"), "other_hormone"),
        _a(
            "igf1", "胰岛素样生长因子-1 (IGF-1)", "ng/mL", _FREE, ("胰岛素样生长因子", "igf-1", "igf1"), "other_hormone"
        ),
        _a("cortisol", "皮质醇 (Cortisol)", "nmol/L", _FREE, ("皮质醇", "cortisol", "cor"), "other_hormone"),
        _a(
            "vitd",
            "总维生素D (25-OH-D)",
            "ng/mL",
            {"ng/mL": 1.0, "nmol/L": 0.4006},
            ("25-羟基维生素d", "25-羟维生素d", "总维生素d", "维生素d3", "维生素d", "25(oh)d", "d/d3", "25-oh-d"),
            "other_hormone",
        ),
        _a(
            "free_e2",
            "游离雌二醇 (Free E2)",
            "pg/mL",
            _FREE,
            ("游离雌二醇", "free e2", "free estradiol"),
            "other_hormone",
        ),
        _a(
            "free_t",
            "游离睾酮 (Free T)",
            "pg/mL",
            {"pg/mL": 1.0, "pmol/L": 0.2884},
            ("游离睾酮", "free testosterone", "free t", "fto", "ft"),
            "other_hormone",
        ),
        _a("shbg", "性激素结合球蛋白 (SHBG)", "nmol/L", {"nmol/L": 1.0}, ("性激素结合球蛋白", "shbg"), "other_hormone"),
        _a("dht", "双氢睾酮 (DHT)", "pg/mL", _FREE, ("双氢睾酮", "二氢睾酮", "dht"), "other_hormone"),
        _a("acth", "促肾上腺皮质激素 (ACTH)", "pg/mL", _FREE, ("促肾上腺皮质激素", "acth"), "other_hormone"),
        _a("e3", "雌三醇 (E3)", "ng/mL", _FREE, ("游离雌三醇", "雌三醇", "estriol", "e3"), "other_hormone"),
        _a(
            "oh2_16",
            "2-羟雌酮/16α-羟雌酮比值",
            "ratio",
            _FREE,
            ("2-羟雌酮/16", "2-oh/16", "2/16比值", "2:16", "2/16"),
            "other_hormone",
        ),
        _a(
            "ohp17",
            "17-羟孕酮 (17-OHP)",
            "ng/mL",
            _FREE,
            ("17α-羟孕酮", "17-羟孕酮", "羟孕酮", "17-ohp", "17ohp"),
            "other_hormone",
        ),
        # ---------------------------------------------------------------- 炎性功能 / 其它
        _a(
            "hscrp",
            "超敏C反应蛋白 (hs-CRP)",
            "mg/L",
            {"mg/L": 1.0, "mg/dL": 10.0},
            ("超敏c反应蛋白", "超敏c-反应蛋白", "c反应蛋白", "hs-crp", "hscrp", "crp"),
            "inflammation",
        ),
        _a("hcy", "同型半胱氨酸 (HCY)", "umol/L", {"umol/L": 1.0}, ("同型半胱氨酸", "hcy"), "inflammation"),
        _a(
            "tas", "总抗氧化状态 (TAS)", "mmol/L", _FREE, ("总抗氧化状态", "总抗氧化能力", "tas", "tac"), "inflammation"
        ),
        _a("sod", "超氧化物歧化酶 (SOD)", "U/mL", _FREE, ("超氧化物歧化酶", "sod"), "inflammation"),
        _a(
            "g6pd",
            "葡萄糖-6-磷酸脱氢酶 (G6PD)",
            "U/gHb",
            _FREE,
            ("6-磷酸葡萄糖脱氢酶", "葡萄糖-6-磷酸脱氢酶", "磷酸葡萄糖脱氢酶", "g6pd"),
            "inflammation",
        ),
        # ---------------------------------------------------------------- 套餐外（疲劳评估）
        _a(
            "b12", "维生素B12", "pg/mL", {"pg/mL": 1.0, "pmol/L": 1.355}, ("维生素b12", "vitb12", "b12"), "inflammation"
        ),
    ]
}


def to_canonical(code: str, value: float, unit: str | None) -> float:
    a = ANALYTES.get(code)
    if a is None:
        raise LabUnitError("ANALYTE_UNKNOWN", f"未知检测项目 '{code}'")
    if a.units is None:
        return value
    norm = normalise_lab_unit(unit) if unit is not None else a.canonical_unit
    if norm is None:
        raise LabUnitError("UNIT_UNKNOWN", f"{a.name_zh}: 无法识别的单位 '{unit}'")
    if norm not in a.units:
        allowed = ", ".join(a.units)
        raise LabUnitError("UNIT_NOT_ALLOWED", f"{a.name_zh}: 单位 '{unit}' 不适用；允许: {allowed}")
    return value * a.units[norm]
