"""Deterministic extraction of lab values from report text (no LLM).

Works on pasted report text or on the text layer of a PDF. Every extracted
value is returned with the source line so the clinician can confirm it;
nothing is used for prescribing until it has been reviewed in the UI.
Scanned (image-only) PDFs have no text layer and need OCR first.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from app.domain.bhrt.labs import ANALYTES, normalise_lab_unit

_NUM = r"(?P<cmp>[<>≤≥]=?)?\s*(?P<num>\d+(?:\.\d+)?)"
_UNIT = r"(?P<unit>[a-zA-Zμµ%/*\d\^]+(?:/[a-zA-Zμµ]+)?)?"
_VALUE_RE = re.compile(_NUM + r"\s*(?:[↑↓HLhl](?![a-zA-Z]))?\s*" + _UNIT)

# alias -> code, longest alias first so "游离睾酮" wins over "睾酮"
_ALIAS_TABLE: list[tuple[str, str]] = sorted(
    ((alias.casefold(), a.code) for a in ANALYTES.values() for alias in a.aliases),
    key=lambda t: -len(t[0]),
)


@dataclass
class ExtractedLab:
    code: str
    name_zh: str
    value: float
    unit: str | None
    unit_recognised: bool
    below_detection: bool
    source_line: str


@dataclass
class ExtractedImaging:
    birads: int | None = None
    endometrial_thickness_mm: float | None = None
    fibroids: bool | None = None
    done: list[str] = field(default_factory=list)  # panel imaging codes mentioned in the report


@dataclass
class ParseResult:
    labs: list[ExtractedLab]
    imaging: ExtractedImaging
    unmatched_lines: int
    warnings: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return s.replace("μ", "u").replace("µ", "u")


def _find_alias(line_cf: str) -> tuple[str, int] | None:
    best: tuple[int, int, str] | None = None  # (pos, -len, code)
    for alias, code in _ALIAS_TABLE:
        if alias.isascii():
            m = re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", line_cf)
            pos = m.start() if m else -1
        else:
            pos = line_cf.find(alias)
        if pos < 0:
            continue
        cand = (pos, -len(alias), code)
        if best is None or cand < best:
            best = cand
    if best is None:
        return None
    return best[2], best[0] - best[1]  # code, end index of alias


def parse_text(text: str) -> ParseResult:
    labs: list[ExtractedLab] = []
    seen: set[str] = set()
    warnings: list[str] = []
    unmatched = 0
    imaging = ExtractedImaging()
    for raw_line in _norm(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        cf = line.casefold()
        _parse_imaging(cf, imaging)
        hit = _find_alias(cf)
        if hit is None:
            unmatched += 1
            continue
        code, end = hit
        rest = line[end:]
        # skip trailing alias text such as "(E2)" or "（TT）" before the number
        rest = re.sub(r"^\s*[\(（][^\)）]{0,20}[\)）]", "", rest)
        a = ANALYTES[code]
        if a.qualitative:
            q = _qualitative(rest)
            if q is None:
                unmatched += 1
                continue
            if code in seen:
                continue
            seen.add(code)
            labs.append(ExtractedLab(code, a.name_zh, q, "定性", True, False, line[:200]))
            continue
        m = _VALUE_RE.search(rest)
        if m is None:
            unmatched += 1
            continue
        value = float(m.group("num"))
        unit_raw = m.group("unit")
        # a reference range like "3.5-5.5" right after the value is not a unit
        if unit_raw and re.fullmatch(r"[\d.]+", unit_raw):
            unit_raw = None
        if unit_raw is None:
            um = re.search(r"([a-zA-Zu%][a-zA-Zu%/*\^\d]*/[a-zA-Z]+|%)", rest[m.end() :])
            unit_raw = um.group(1) if um else None
        norm_unit = normalise_lab_unit(unit_raw) if unit_raw else None
        if code == "hct" and norm_unit is None and value < 1:
            norm_unit = "L/L"
        if code in seen:
            warnings.append(f"{a.name_zh} 在报告中出现多次，仅保留第一次：请人工核对")
            continue
        seen.add(code)
        labs.append(
            ExtractedLab(
                code=code,
                name_zh=a.name_zh,
                value=value,
                unit=norm_unit or unit_raw,
                unit_recognised=a.units is None or (norm_unit is not None and norm_unit in a.units),
                below_detection=(m.group("cmp") or "").startswith(("<", "≤")),
                source_line=line[:200],
            )
        )
    for lab in labs:
        if not lab.unit_recognised:
            warnings.append(f"{lab.name_zh}: 单位未识别（{lab.unit or '无'}），请人工确认")
    return ParseResult(labs=labs, imaging=imaging, unmatched_lines=unmatched, warnings=warnings)


def _qualitative(rest: str) -> float | None:
    r = rest.casefold()
    if "阳性" in r or "(+)" in r or re.search(r"(?<![a-z])pos", r):
        return 1.0
    if "阴性" in r or "(-)" in r or re.search(r"(?<![a-z])neg", r):
        return 0.0
    return None


_IMAGING_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("us_thyroid", ("甲状腺超声", "甲状腺彩超", "甲状腺b超")),
    ("us_abdomen", ("腹部超声", "腹部彩超", "腹部b超", "肝胆胰脾", "肝胆脾胰")),
    ("echo", ("超声心动图", "心脏彩超", "心脏超声")),
    ("us_prostate", ("前列腺超声", "前列腺彩超", "前列腺b超")),
    ("us_breast", ("乳腺超声", "乳腺彩超", "乳腺b超")),
    ("us_pelvic", ("子宫附件", "子宫、卵巢", "子宫卵巢", "妇科超声", "经阴道超声", "盆腔超声")),
    ("mammogram", ("钼靶", "乳腺x线", "mammogra")),
    ("dexa", ("骨密度",)),
    ("mri_brain", ("颅脑mri", "头颅mri", "颅脑磁共振", "头颅磁共振")),
    ("ct_lung", ("肺部ct", "胸部ct", "肺ct", "胸部 ct", "肺部 ct")),
    ("ct_heart", ("心脏ct", "冠脉ct", "冠状动脉ct", "钙化积分")),
)


def _parse_imaging(cf: str, img: ExtractedImaging) -> None:
    for code, kws in _IMAGING_KEYWORDS:
        if code not in img.done and any(k in cf for k in kws):
            img.done.append(code)
    m = re.search(r"bi-?rads\s*[:：]?\s*(?:分类|类)?\s*([0-6])", cf)
    if m and img.birads is None:
        img.birads = int(m.group(1))
    m = re.search(r"内膜[^\d]{0,8}?(\d+(?:\.\d+)?)\s*(mm|cm)", cf)
    if m and img.endometrial_thickness_mm is None:
        v = float(m.group(1))
        img.endometrial_thickness_mm = v * 10 if m.group(2) == "cm" else v
    if ("肌瘤" in cf or "fibroid" in cf) and not re.search(r"未见.{0,6}肌瘤", cf):
        img.fibroids = True


class PdfError(ValueError):
    pass


MAX_PDF_BYTES = 10 * 1024 * 1024


def pdf_text(b64: str) -> str:
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise PdfError("PDF 文件编码无效") from e
    if len(data) > MAX_PDF_BYTES:
        raise PdfError("PDF 超过 10 MB")
    if not data.startswith(b"%PDF"):
        raise PdfError("不是有效的 PDF 文件")
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:  # noqa: BLE001 - pypdf raises many types on malformed input
        raise PdfError("PDF 无法读取") from e
