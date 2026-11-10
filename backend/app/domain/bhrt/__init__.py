"""BHRT prescription-draft engine (deterministic, rule-based, no LLM).

Pipeline: report ingestion -> completeness check -> risk analysis / safety
gate -> stage classification -> symptom mapping -> route selection -> dose
builder -> monitoring plan -> prescription draft (physician must sign).

Clinical basis: uSciTec BHRT Clinical Decision Framework. All thresholds live
in :mod:`app.domain.bhrt.rules` and the product catalogue in
:mod:`app.domain.bhrt.products` so the clinic can adjust them in one place.
"""
