"""Independent reference implementation of Levine 2018 PhenoAge.

Deliberately shares NO code with ``app.domain``:
* own coefficient table (transcribed separately from the paper),
* arbitrary-precision ``decimal`` arithmetic; the precision is raised adaptively so
  that ``1 - M`` (which can be ~1e-3000 for extreme profiles) never underflows,
* the "1 - exp(-exp(xb) * (exp(120*gamma) - 1) / gamma)" mortality form
  evaluated literally, followed by the literal PhenoAge inverse.

Inputs are in the paper's units: albumin g/L, creatinine umol/L,
glucose mmol/L, CRP mg/dL (natural log), lymphocyte %, MCV fL, RDW %,
ALP U/L, WBC 1000 cells/uL, age years.
"""

from decimal import Decimal, localcontext

D = Decimal
_W = {
    "albumin": D("-0.0336"),
    "creatinine": D("0.0095"),
    "glucose": D("0.1953"),
    "crp": D("0.0954"),  # applied to ln(CRP mg/dL)
    "lymphocyte_pct": D("-0.0120"),
    "mcv": D("0.0268"),
    "rdw": D("0.3306"),
    "alp": D("0.00188"),
    "wbc": D("0.0554"),
    "age": D("0.0804"),
}
_B0 = D("-19.907")
_GAMMA = D("0.0076927")


def reference_phenoage(values: dict[str, float]) -> tuple[Decimal, Decimal, Decimal]:
    """Return (phenoage, mortality_score, xb) at high precision."""
    with localcontext() as ctx:
        ctx.prec = 80
        xb = _B0
        for k, w in _W.items():
            v = D(repr(values[k]))
            if k == "crp":
                v = v.ln()
            xb += w * v
        # digits needed so that exp(-H) is still distinguishable from 0 next to 1
        hazard_estimate = float(xb.exp()) * 200
        ctx.prec = int(hazard_estimate / 2.302585) + 80
        m = 1 - (-(xb.exp()) * ((D(120) * _GAMMA).exp() - 1) / _GAMMA).exp()
        pa = D("141.50225") + (D("-0.00553") * (1 - m).ln()).ln() / D("0.090165")
        ctx.prec = 40
        return +pa, +m, +xb
