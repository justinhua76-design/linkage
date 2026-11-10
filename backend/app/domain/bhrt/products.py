"""DKi BHRT product catalogue — mirrors the「BHRT Prescription Form / 生物同源性荷尔蒙处方」.

All creams: 1 g = 1 mL; Topi-Click 1 转 = 250 mg = 0.25 mL (confirmed by the
clinic); standard dispensing quantity 30 mL ≈ 120 转.
"""

from __future__ import annotations

from dataclasses import dataclass

CLICK_MG_CREAM = 250.0
CLICK_ML = 0.25
CONTAINER_ML = 30
CLICKS_PER_CONTAINER = int(CONTAINER_ML / CLICK_ML)  # 120


@dataclass(frozen=True)
class Product:
    code: str
    hormone_en: str
    hormone_zh: str
    strength: str  # as printed on the form (mg/mL)
    equivalent: str  # as printed on the form (%)
    mg_per_ml: float | None  # total active per mL
    e2_mg_per_ml: float = 0.0
    e3_mg_per_ml: float = 0.0
    route: str = "transdermal"  # transdermal | oral | pellet
    on_form: bool = True  # appears in the form's Hormone Selection table

    @property
    def name_zh(self) -> str:
        return f"{self.hormone_zh} {self.equivalent}" if self.on_form else self.hormone_zh

    def mg_per_click(self) -> float | None:
        return None if self.mg_per_ml is None else self.mg_per_ml * CLICK_ML


def _cream(code, en, zh, strength, eq, mg, e2=0.0, e3=0.0) -> Product:  # noqa: ANN001
    return Product(code, en, zh, strength, eq, mg, e2, e3)


PRODUCTS: dict[str, Product] = {
    p.code: p
    for p in [
        _cream("t_1", "Testosterone", "睾酮", "10 mg/mL", "1%", 10.0),
        _cream("t_4", "Testosterone", "睾酮", "40 mg/mL", "4%", 40.0),
        _cream("t_8", "Testosterone", "睾酮", "80 mg/mL", "8%", 80.0),
        _cream("t_10", "Testosterone", "睾酮", "100 mg/mL", "10%", 100.0),
        _cream("t_20", "Testosterone", "睾酮", "200 mg/mL", "20%", 200.0),
        _cream("prog_5", "Progesterone", "黄体酮", "50 mg/mL", "5%", 50.0),
        _cream("prog_10", "Progesterone", "黄体酮", "100 mg/mL", "10%", 100.0),
        _cream(
            "biest19_025",
            "Biest (1:9)",
            "双雌 (1:9)",
            "E2 0.25 + E3 2.25 mg/mL",
            "0.25% Total Estrogens",
            2.5,
            0.25,
            2.25,
        ),
        _cream(
            "biest19_05", "Biest (1:9)", "双雌 (1:9)", "E2 0.50 + E3 4.50 mg/mL", "0.50% Total Estrogens", 5.0, 0.5, 4.5
        ),
        _cream(
            "biest28_025",
            "Biest (2:8)",
            "双雌 (2:8)",
            "E2 0.50 + E3 2.00 mg/mL",
            "0.25% Total Estrogens",
            2.5,
            0.5,
            2.0,
        ),
        _cream(
            "biest28_05", "Biest (2:8)", "双雌 (2:8)", "E2 1.00 + E3 4.00 mg/mL", "0.50% Total Estrogens", 5.0, 1.0, 4.0
        ),
        _cream("estradiol_001", "Estradiol", "雌二醇", "0.1 mg/mL", "0.01%", 0.1, 0.1, 0.0),
        _cream("estriol_001", "Estriol", "雌三醇", "0.1 mg/mL", "0.01%", 0.1, 0.0, 0.1),
        _cream("dhea_5", "DHEA", "DHEA", "50 mg/mL", "5%", 50.0),
        _cream("dhea_10", "DHEA", "DHEA", "100 mg/mL", "10%", 100.0),
        _cream("chrysin_5", "Chrysin", "白杨素", "50 mg/mL", "5%", 50.0),
        _cream("chrysin_10", "Chrysin", "白杨素", "100 mg/mL", "10%", 100.0),
        # not on the cream form
        Product(
            "prog_oral_100",
            "Oral micronized progesterone",
            "口服微粒化黄体酮胶囊",
            "100 mg/粒",
            "—",
            None,
            route="oral",
            on_form=False,
        ),
        Product(
            "e2_pellet",
            "Estradiol pellet",
            "雌二醇 Pellet",
            "6 / 12.5 / 25 mg",
            "—",
            None,
            route="pellet",
            on_form=False,
        ),
        Product(
            "t_pellet",
            "Testosterone pellet",
            "睾酮 Pellet",
            "25 / 50 / 75 mg",
            "—",
            None,
            route="pellet",
            on_form=False,
        ),
    ]
}

FORM_GENERAL_INSTRUCTIONS = [
    ("Apply at approximately the same time each day.", "每天尽量于相同时间使用。"),
    ("Massage until fully absorbed.", "轻轻按摩至完全吸收。"),
    ("Wash hands after application.", "使用后请洗手。"),
    ("1 g cream = 1 mL cream.", "1 克乳膏 = 1 毫升乳膏。"),
]
