"""DKi「健康管理临床体检项目 - BHRT」 panel (VS.25.07), items 1-115.

Each item lists the analyte codes that satisfy it (any one), which package
it belongs to (female standard / male) and whether it is *decision-critical*:
decision-critical items block the prescription draft when missing; the other
package items are reported as 套餐缺项 but do not block dosing (set
``PACKAGE_ITEMS_BLOCK = True`` in rules.py to make the whole package mandatory).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelItem:
    no: int
    category: str
    name: str
    codes: tuple[str, ...]  # lab analyte codes; empty for imaging
    female: bool
    male: bool
    imaging_code: str | None = None


def _l(no: int, cat: str, name: str, codes: str | tuple[str, ...], f: bool = True, m: bool = True) -> PanelItem:
    return PanelItem(no, cat, name, (codes,) if isinstance(codes, str) else codes, f, m)


def _i(no: int, cat: str, name: str, code: str, f: bool = True, m: bool = True) -> PanelItem:
    return PanelItem(no, cat, name, (), f, m, code)


PANEL: tuple[PanelItem, ...] = (
    _l(1, "血脂", "TG 甘油三酯", "tg"),
    _l(2, "血脂", "TC 总胆固醇", "tc"),
    _l(3, "血脂", "HDL-C 高密度脂蛋白胆固醇", "hdl"),
    _l(4, "血脂", "LDL-C 低密度脂蛋白胆固醇", "ldl"),
    _l(5, "血脂", "APOAI 载脂蛋白A1", "apoa1"),
    _l(6, "血脂", "APOB 载脂蛋白B", "apob"),
    _l(7, "血糖", "GLU 空腹血糖", "glucose"),
    _l(8, "血糖", "INS 胰岛素", "insulin"),
    _l(9, "血糖", "HbA1c 糖化血红蛋白", "hba1c"),
    _l(10, "肾功能", "Cr 肌酐", "creatinine"),
    _l(11, "肾功能", "UA 尿酸", "uric_acid"),
    _l(12, "肾功能", "Urea 尿素氮", "urea"),
    _l(13, "肝功能", "D-BIL 直接胆红素", "dbil"),
    _l(14, "肝功能", "I-BIL 间接胆红素", "ibil"),
    _l(15, "肝功能", "T-BIL 总胆红素", "tbil"),
    _l(16, "肝功能", "ALT 谷丙转氨酶", "alt"),
    _l(17, "肝功能", "AST 谷草转氨酶", "ast"),
    _l(18, "肝功能", "ALP 碱性磷酸酶", "alp"),
    _l(19, "肝功能", "AST/ALT", ("ast_alt",)),
    _l(20, "肝功能", "γ-GT 谷氨酰转肽酶", "ggt"),
    _l(21, "肝功能", "TP 总蛋白", "tp"),
    _l(22, "肝功能", "ALB 白蛋白", "alb"),
    _l(23, "肝功能", "GLB 球蛋白", "glb"),
    _l(24, "乙肝", "HBsAg 乙肝表面抗原", "hbsag"),
    _l(25, "乙肝", "HBsAb 乙肝表面抗体", "hbsab"),
    _l(26, "乙肝", "HBeAg 乙肝e抗原", "hbeag"),
    _l(27, "乙肝", "HBeAb 乙肝e抗体", "hbeab"),
    _l(28, "乙肝", "HBcAb 乙肝核心抗体IgG", "hbcab"),
    _l(29, "免疫三项", "IgM 免疫球蛋白M", "igm"),
    _l(30, "免疫三项", "IgA 免疫球蛋白A", "iga"),
    _l(31, "免疫三项", "IgG 免疫球蛋白G", "igg"),
    _l(32, "甲状腺八项", "FT3 游离三碘甲状腺原氨酸", "ft3"),
    _l(33, "甲状腺八项", "FT4 游离甲状腺素", "ft4"),
    _l(34, "甲状腺八项", "T3 三碘甲状腺原氨酸", "t3"),
    _l(35, "甲状腺八项", "T4 甲状腺素", "t4"),
    _l(36, "甲状腺八项", "TSH 促甲状腺激素", "tsh"),
    _l(37, "甲状腺八项", "TGA 甲状腺球蛋白抗体", "tgab"),
    _l(38, "甲状腺八项", "TMA 甲状腺微粒体抗体", "tmab"),
    _l(39, "甲状腺八项", "TPOA 甲状腺过氧化物酶抗体", "tpoab"),
    _l(40, "血常规", "WBC 白细胞数", "wbc"),
    _l(41, "血常规", "NEU% 中性粒细胞百分比", "neu_pct"),
    _l(42, "血常规", "NEU# 中性粒细胞绝对数", "neu_abs"),
    _l(43, "血常规", "LY% 淋巴细胞百分比", "ly_pct"),
    _l(44, "血常规", "LY# 淋巴细胞绝对数", "ly_abs"),
    _l(45, "血常规", "EOS% 嗜酸性粒细胞百分比", "eos_pct"),
    _l(46, "血常规", "EOS# 嗜酸性粒细胞绝对值", "eos_abs"),
    _l(47, "血常规", "BAS% 嗜碱性粒细胞百分比", "bas_pct"),
    _l(48, "血常规", "BAS# 嗜碱性粒细胞绝对值", "bas_abs"),
    _l(49, "血常规", "MON% 单核细胞百分比", "mon_pct"),
    _l(50, "血常规", "MON# 单核细胞绝对值", "mon_abs"),
    _l(51, "血常规", "RBC 红细胞", "rbc"),
    _l(52, "血常规", "HGB 血红蛋白", "hb"),
    _l(53, "血常规", "HCT 红细胞压积", "hct"),
    _l(54, "血常规", "MCV 平均红细胞体积", "mcv"),
    _l(55, "血常规", "MCHC 平均红细胞血红蛋白浓度", "mchc"),
    _l(56, "血常规", "MCH 平均红细胞血红蛋白含量", "mch"),
    _l(57, "血常规", "RDW-CV 红细胞分布宽度变异系数", "rdw_cv"),
    _l(58, "血常规", "RDW-SD 红细胞分布宽度(SD)", "rdw_sd"),
    _l(59, "血常规", "PLT 血小板计数", "plt"),
    _l(60, "血常规", "PDW 血小板分布宽度", "pdw"),
    _l(61, "血常规", "MPV 血小板平均体积", "mpv"),
    _l(62, "血常规", "PCT 血小板比积", "pct"),
    _l(63, "血常规", "P-LCR 大血小板比率", "p_lcr"),
    _l(64, "血常规", "P-LCC 大血小板数目", "p_lcc"),
    _l(65, "肿瘤标记物", "Fer 铁蛋白", "ferritin"),
    _l(66, "肿瘤标记物", "AFP 甲胎蛋白", "afp"),
    _l(67, "肿瘤标记物", "CEA 癌胚抗原", "cea"),
    _l(68, "肿瘤标记物", "CA19-9 糖类抗原", "ca199"),
    _l(69, "肿瘤标记物", "CA125 癌抗原", "ca125"),
    _l(70, "肿瘤标记物", "CA15-3 肿瘤抗原", "ca153"),
    _l(71, "肿瘤标记物", "TNF-α 肿瘤坏死因子", "tnfa"),
    _l(72, "肿瘤标记物", "TPSA 总前列腺特异性抗原", "psa", f=False),
    _l(73, "肿瘤标记物", "FPSA 游离前列腺特异性抗原", "fpsa", f=False),
    _l(74, "电解质六项", "K 钾", "k"),
    _l(75, "电解质六项", "Na 钠", "na"),
    _l(76, "电解质六项", "Cl 氯", "cl"),
    _l(77, "电解质六项", "Mg 镁", "mg"),
    _l(78, "电解质六项", "Ca 钙", "ca"),
    _l(79, "电解质六项", "P 磷", "phos"),
    _l(80, "性激素", "FSH 促卵泡生成素", "fsh"),
    _l(81, "性激素", "LH 促黄体生成素", "lh"),
    _l(82, "性激素", "PRL 催乳素", "prl"),
    _l(83, "性激素", "TES 睾酮", "total_t"),
    _l(84, "性激素", "E2 雌二醇", "e2"),
    _l(85, "性激素", "P 孕酮", "progesterone"),
    _l(86, "卵巢功能", "AMH 抗缪勒管激素", "amh", m=False),
    _l(87, "其它激素", "DHEA 脱氢表雄酮 (DHEA、DHEA-S)", ("dheas", "dhea")),
    _l(88, "其它激素", "IGF-1 胰岛素样生长因子-1", "igf1"),
    _l(89, "其它激素", "Cortisol 皮质醇", "cortisol"),
    _l(90, "其它激素", "D/D3 总维生素D、D3", "vitd"),
    _l(91, "其它激素", "Free E2 游离雌二醇", "free_e2", m=False),
    _l(92, "其它激素", "Free T 游离睾酮", "free_t"),
    _l(93, "其它激素", "SHBG 性激素结合球蛋白", "shbg"),
    _l(94, "其它激素", "DHT 双氢睾酮", "dht", f=False),
    _l(95, "其它激素", "ACTH 促肾上腺皮质激素", "acth"),
    _l(96, "其它激素", "E3 雌三醇", "e3", m=False),
    _l(97, "其它激素", "2-羟雌酮/16-羟雌酮", "oh2_16", m=False),
    _l(98, "其它激素", "17-羟孕酮", "ohp17"),
    _l(99, "炎性功能", "Hs-CRP 超敏C反应蛋白", "hscrp"),
    _l(100, "炎性功能", "HCY 同型半胱氨酸", "hcy"),
    _l(101, "炎性功能", "TAS 总抗氧化状态", "tas"),
    _l(102, "其它", "SOD 超氧化物歧化酶", "sod"),
    _l(103, "其它", "G6PD 6-磷酸葡萄糖脱氢酶", "g6pd"),
    _i(105, "B超", "甲状腺超声", "us_thyroid"),
    _i(106, "B超", "腹部超声（肝、胆、脾、胰、肾）", "us_abdomen"),
    _i(107, "B超", "超声心动图", "echo", f=False),
    _i(108, "B超", "前列腺超声（男）", "us_prostate", f=False),
    _i(109, "B超", "乳腺超声（女）", "us_breast", m=False),
    _i(110, "B超", "子宫、卵巢超声（女）", "us_pelvic", m=False),
    _i(111, "钼靶", "乳腺钼靶", "mammogram", m=False),
    _i(112, "骨密度 X 光", "骨密度筛查", "dexa"),
    _i(113, "MRI", "颅脑 MRI", "mri_brain"),
    _i(114, "CT", "肺部 CT", "ct_lung"),
    _i(115, "CT", "心脏 CT", "ct_heart"),
)

IMAGING_ITEMS = {p.imaging_code: p for p in PANEL if p.imaging_code}


def items_for(sex: str) -> list[PanelItem]:
    return [p for p in PANEL if (p.female if sex == "female" else p.male)]
