"""Lab analytes used by the BHRT engine: names, aliases, units, conversions."""

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
    # normalised unit -> factor (canonical = value * factor)
    units: dict[str, float]
    # spellings found in Chinese / English lab reports (matched case-insensitively)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    group: str = "other"


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
    "iu/l": "IU/L",
    "miu/ml": "IU/L",
    "mu/ml": "IU/L",
    "u/l": "U/L",
    "miu/l": "mIU/L",
    "uiu/ml": "mIU/L",
    "mu/l": "mIU/L",
    "g/l": "g/L",
    "g/dl": "g/dL",
    "%": "%",
    "l/l": "L/L",
    "pmol/l*": "pmol/L",
}


def normalise_lab_unit(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    key = _canonicalise(str(raw))
    return _UNIT_ALIASES.get(key)


ANALYTES: dict[str, Analyte] = {
    a.code: a
    for a in [
        # ---- sex hormones
        Analyte(
            "e2", "雌二醇 (E2)", "pg/mL", {"pg/mL": 1.0, "pmol/L": 0.2724}, ("雌二醇", "estradiol", "e2"), "hormone"
        ),
        Analyte(
            "progesterone",
            "孕酮 (P)",
            "ng/mL",
            {"ng/mL": 1.0, "nmol/L": 0.3145},
            ("孕酮", "黄体酮", "progesterone", "prog"),
            "hormone",
        ),
        Analyte(
            "total_t",
            "总睾酮 (TT)",
            "nmol/L",
            {"nmol/L": 1.0, "ng/dL": 0.03467, "ng/mL": 3.467},
            ("总睾酮", "睾酮", "total testosterone", "testosterone", "tt", "testo"),
            "hormone",
        ),
        Analyte(
            "free_t",
            "游离睾酮 (FT)",
            "pg/mL",
            {"pg/mL": 1.0, "pmol/L": 0.2884},
            ("游离睾酮", "free testosterone", "fto", "ft"),
            "hormone",
        ),
        Analyte("shbg", "性激素结合球蛋白 (SHBG)", "nmol/L", {"nmol/L": 1.0}, ("性激素结合球蛋白", "shbg"), "hormone"),
        Analyte(
            "dheas",
            "硫酸脱氢表雄酮 (DHEA-S)",
            "ug/dL",
            {"ug/dL": 1.0, "umol/L": 36.81},
            ("硫酸脱氢表雄酮", "脱氢表雄酮硫酸酯", "dhea-s", "dheas", "dhea-so4"),
            "hormone",
        ),
        Analyte(
            "fsh",
            "促卵泡生成素 (FSH)",
            "IU/L",
            {"IU/L": 1.0},
            ("促卵泡生成素", "促卵泡激素", "卵泡刺激素", "卵泡生成素", "fsh"),
            "hormone",
        ),
        Analyte(
            "lh",
            "促黄体生成素 (LH)",
            "IU/L",
            {"IU/L": 1.0},
            ("促黄体生成素", "黄体生成素", "促黄体激素", "lh"),
            "hormone",
        ),
        # ---- thyroid
        Analyte("tsh", "促甲状腺激素 (TSH)", "mIU/L", {"mIU/L": 1.0}, ("促甲状腺激素", "促甲状腺素", "tsh"), "thyroid"),
        Analyte(
            "ft4",
            "游离甲状腺素 (FT4)",
            "pmol/L",
            {"pmol/L": 1.0, "ng/dL": 12.87},
            ("游离甲状腺素", "游离t4", "ft4"),
            "thyroid",
        ),
        # ---- CMP
        Analyte(
            "alt",
            "丙氨酸氨基转移酶 (ALT)",
            "U/L",
            {"U/L": 1.0, "IU/L": 1.0},
            ("丙氨酸氨基转移酶", "谷丙转氨酶", "alt", "gpt"),
            "cmp",
        ),
        Analyte(
            "ast",
            "天门冬氨酸氨基转移酶 (AST)",
            "U/L",
            {"U/L": 1.0, "IU/L": 1.0},
            ("天门冬氨酸氨基转移酶", "天冬氨酸氨基转移酶", "谷草转氨酶", "ast", "got"),
            "cmp",
        ),
        Analyte(
            "creatinine",
            "肌酐 (Cr)",
            "umol/L",
            {"umol/L": 1.0, "mg/dL": 88.4},
            ("肌酐", "creatinine", "crea", "cr"),
            "cmp",
        ),
        Analyte(
            "glucose",
            "空腹血糖 (GLU)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.0555},
            ("空腹血糖", "空腹葡萄糖", "葡萄糖", "glucose", "glu"),
            "cmp",
        ),
        Analyte("hba1c", "糖化血红蛋白 (HbA1c)", "%", {"%": 1.0}, ("糖化血红蛋白", "hba1c"), "cmp"),
        # ---- lipids
        Analyte(
            "tc",
            "总胆固醇 (TC)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("总胆固醇", "胆固醇", "tc", "chol"),
            "lipid",
        ),
        Analyte(
            "tg",
            "甘油三酯 (TG)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.01129},
            ("甘油三酯", "三酰甘油", "tg", "trig"),
            "lipid",
        ),
        Analyte(
            "ldl",
            "低密度脂蛋白胆固醇 (LDL-C)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("低密度脂蛋白胆固醇", "低密度脂蛋白", "ldl-c", "ldl"),
            "lipid",
        ),
        Analyte(
            "hdl",
            "高密度脂蛋白胆固醇 (HDL-C)",
            "mmol/L",
            {"mmol/L": 1.0, "mg/dL": 0.02586},
            ("高密度脂蛋白胆固醇", "高密度脂蛋白", "hdl-c", "hdl"),
            "lipid",
        ),
        # ---- CBC
        Analyte("hb", "血红蛋白 (Hb)", "g/L", {"g/L": 1.0, "g/dL": 10.0}, ("血红蛋白", "hgb", "hb"), "cbc"),
        Analyte(
            "hct",
            "红细胞压积 (Hct)",
            "%",
            {"%": 1.0, "L/L": 100.0},
            ("红细胞压积", "红细胞比容", "红细胞比积", "hct"),
            "cbc",
        ),
        # ---- men
        Analyte(
            "psa",
            "前列腺特异性抗原 (PSA)",
            "ng/mL",
            {"ng/mL": 1.0},
            ("总前列腺特异性抗原", "前列腺特异性抗原", "tpsa", "psa"),
            "male",
        ),
        # ---- fatigue / brain-fog work-up
        Analyte(
            "vitd",
            "25-羟维生素D",
            "ng/mL",
            {"ng/mL": 1.0, "nmol/L": 0.4006},
            ("25-羟基维生素d", "25-羟维生素d", "25(oh)d", "维生素d"),
            "other",
        ),
        Analyte("ferritin", "铁蛋白", "ng/mL", {"ng/mL": 1.0}, ("铁蛋白", "ferritin", "ferr"), "other"),
        Analyte("b12", "维生素B12", "pg/mL", {"pg/mL": 1.0, "pmol/L": 1.355}, ("维生素b12", "vitb12", "b12"), "other"),
    ]
}


def to_canonical(code: str, value: float, unit: str | None) -> float:
    a = ANALYTES.get(code)
    if a is None:
        raise LabUnitError("ANALYTE_UNKNOWN", f"未知检测项目 '{code}'")
    norm = normalise_lab_unit(unit) if unit is not None else a.canonical_unit
    if norm is None:
        raise LabUnitError("UNIT_UNKNOWN", f"{a.name_zh}: 无法识别的单位 '{unit}'")
    if norm not in a.units:
        allowed = ", ".join(a.units)
        raise LabUnitError("UNIT_NOT_ALLOWED", f"{a.name_zh}: 单位 '{unit}' 不适用；允许: {allowed}")
    return value * a.units[norm]
