"""uSciTec BHRT product catalogue.

Entries with ``confirmed=False`` are placeholders whose specification has not
yet been supplied by the clinic. The engine still recommends the therapy but
prints "规格待确认" instead of a click/capsule count, so no dose is ever
computed from an invented strength.
"""

from __future__ import annotations

from dataclasses import dataclass

# Topi-Click 30 g dispenser: 1 转 (click) = 250 mg cream, ~120 转 per container.
# Verify 1 转 = 250 mg against the dispensing device before clinical use.
CLICK_MG_CREAM = 250.0
CLICKS_PER_CONTAINER = 120


@dataclass(frozen=True)
class Product:
    code: str
    name_zh: str
    route: str  # transdermal | oral | vaginal | pellet
    strength: str
    package: str
    # active mg delivered per unit (click / capsule / pellet); None = unknown
    mg_per_unit: float | None
    unit_label: str
    confirmed: bool = True
    note: str = ""


PRODUCTS: dict[str, Product] = {
    p.code: p
    for p in [
        Product(
            "biest_025",
            "Bi-Est 双雌乳膏 0.25% (E3:E2 = 80:20)",
            "transdermal",
            "0.25%",
            "Topi-Click 30 g",
            0.625,
            "转",
            note="每转 0.625 mg Bi-Est = E2 0.125 mg + E3 0.5 mg",
        ),
        Product(
            "biest_05",
            "Bi-Est 双雌乳膏 0.5% (E3:E2 = 80:20)",
            "transdermal",
            "0.5%",
            "Topi-Click 30 g",
            1.25,
            "转",
            note="每转 1.25 mg Bi-Est = E2 0.25 mg + E3 1.0 mg",
        ),
        Product(
            "prog_cream_5", "黄体酮乳膏 5%", "transdermal", "5%", "Topi-Click 30 g", 12.5, "转", note="每转 12.5 mg"
        ),
        Product(
            "prog_cream_10", "黄体酮乳膏 10%", "transdermal", "10%", "Topi-Click 30 g", 25.0, "转", note="每转 25 mg"
        ),
        Product("prog_oral_100", "口服微粒化黄体酮胶囊 100 mg", "oral", "100 mg", "胶囊", 100.0, "粒"),
        Product(
            "prog_vaginal",
            "阴道用黄体酮",
            "vaginal",
            "规格待确认",
            "待确认",
            None,
            "次",
            confirmed=False,
            note="请提供剂型（栓剂/凝胶/胶囊阴道给药）与单次剂量",
        ),
        Product(
            "t_cream_f",
            "睾酮乳膏（女性）",
            "transdermal",
            "规格待确认",
            "Topi-Click 30 g",
            None,
            "转",
            confirmed=False,
            note="请提供浓度；女性目标经皮剂量约 0.3 mg/日（2019 全球共识）",
        ),
        Product(
            "t_cream_m",
            "睾酮乳膏（男性）",
            "transdermal",
            "规格待确认",
            "Topi-Click 30 g",
            None,
            "转",
            confirmed=False,
            note="请提供浓度及男性起始方案",
        ),
        Product(
            "estriol_vaginal",
            "阴道用雌三醇乳膏",
            "vaginal",
            "规格待确认",
            "待确认",
            None,
            "次",
            confirmed=False,
            note="用于仅泌尿生殖道症状（GSM）的局部治疗",
        ),
        Product("e2_pellet", "雌二醇 Pellet", "pellet", "6 / 12.5 / 25 mg", "单粒", None, "mg"),
        Product("t_pellet", "睾酮 Pellet", "pellet", "25 / 50 / 75 mg", "单粒", None, "mg"),
    ]
}
