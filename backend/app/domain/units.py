"""Strict unit normalisation and conversion.

Design rules
------------
* Only explicitly whitelisted unit spellings are accepted. Anything else is a
  hard error - we never guess a unit.
* Each biomarker has exactly one canonical unit (the unit used by the
  Levine 2018 PhenoAge model). Conversions are multiplicative factors from an
  accepted unit to that canonical unit, documented in docs/CLINICAL_MODEL.md.
* Units that are *physically* different quantities (e.g. RDW-SD in fL instead
  of RDW-CV in %) are rejected rather than converted.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


class UnitError(ValueError):
    """Raised when a unit is unknown or not allowed for a biomarker."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# Spelling variants -> normalised token. Keys are compared after
# canonicalisation (NFKC, whitespace removed, case-folded, micro sign unified).
_ALIASES: dict[str, str] = {
    # mass concentration
    "g/l": "g/L",
    "g/dl": "g/dL",
    "mg/dl": "mg/dL",
    "mg/l": "mg/L",
    # molar concentration
    "umol/l": "umol/L",
    "mmol/l": "mmol/L",
    # enzyme activity
    "u/l": "U/L",
    "iu/l": "U/L",
    "ukat/l": "ukat/L",
    # percentages
    "%": "%",
    "percent": "%",
    # volume
    "fl": "fL",
    "um3": "fL",
    # counts
    "10^3/ul": "10^3/uL",
    "10*3/ul": "10^3/uL",
    "10e3/ul": "10^3/uL",
    "k/ul": "10^3/uL",
    "x10^3/ul": "10^3/uL",
    "10^9/l": "10^9/L",
    "10*9/l": "10^9/L",
    "x10^9/l": "10^9/L",
    "g/l(cells)": "10^9/L",
    "cells/ul": "cells/uL",
    "/ul": "cells/uL",
    # time
    "years": "years",
    "year": "years",
    "y": "years",
    "yr": "years",
}


def _canonicalise(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw)
    # NFKC maps U+00B5 (micro sign) to U+03BC (greek mu); unify both to "u".
    s = s.replace("μ", "u").replace("µ", "u")
    s = s.replace("×", "x")  # multiplication sign
    s = re.sub(r"\s+", "", s)
    return s.casefold()


def normalise_unit(raw: str | None) -> str:
    """Return the normalised spelling of ``raw`` or raise :class:`UnitError`."""
    if raw is None or not str(raw).strip():
        raise UnitError("UNIT_MISSING", "未提供单位 (unit is required)")
    key = _canonicalise(str(raw))
    if key not in _ALIASES:
        raise UnitError("UNIT_UNKNOWN", f"无法识别的单位 '{raw}' (unknown unit)")
    return _ALIASES[key]


@dataclass(frozen=True)
class Conversion:
    unit: str
    factor: float  # canonical = value * factor
    note: str = ""


def convert(value: float, unit: str, canonical_unit: str, allowed: tuple[Conversion, ...]) -> tuple[float, float]:
    """Convert ``value`` given in normalised ``unit`` to the canonical unit.

    Returns ``(canonical_value, factor)``.
    """
    for conv in allowed:
        if conv.unit == unit:
            return value * conv.factor, conv.factor
    allowed_units = ", ".join(c.unit for c in allowed)
    raise UnitError(
        "UNIT_NOT_ALLOWED",
        f"单位 '{unit}' 不适用于该指标；允许的单位: {allowed_units} (canonical: {canonical_unit})",
    )
