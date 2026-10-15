from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import request_id
from app.core.config import Settings, get_settings
from app.core.security import Permission, Principal, require
from app.db.models import BioAgeResult, LabResult, Patient
from app.db.session import get_db
from app.domain.biomarkers import (
    AGE_HARD_HIGH,
    AGE_HARD_LOW,
    AGE_TRAINING_HIGH,
    AGE_TRAINING_LOW,
    BIOMARKERS,
    BiomarkerCode,
)
from app.domain.validation import RawMeasurement
from app.schemas.bioage import (
    BiomarkerCatalog,
    BiomarkerMeta,
    MeasurementOut,
    ModelInfo,
    PhenoAgeRejected,
    PhenoAgeRequest,
    PhenoAgeResponse,
)
from app.schemas.common import IssueOut
from app.services import audit
from app.services.phenoage_service import model_info, run_phenoage

router = APIRouter(prefix="/bioage", tags=["bioage"])
log = logging.getLogger("app.bioage")


@router.get("/biomarkers", response_model=BiomarkerCatalog)
def biomarker_catalog(
    settings: Settings = Depends(get_settings),
    _: Principal = Depends(require(Permission.BIOAGE_READ)),
) -> BiomarkerCatalog:
    return BiomarkerCatalog(
        model=ModelInfo(**model_info()),
        biomarkers=[
            BiomarkerMeta(
                code=d.code.value,
                name_en=d.name_en,
                name_zh=d.name_zh,
                canonical_unit=d.canonical_unit,
                allowed_units=d.allowed_units,
                plausible_low=d.plausible_low,
                plausible_high=d.plausible_high,
                reference_low=d.reference_low,
                reference_high=d.reference_high,
                supports_lod=d.code is BiomarkerCode.CRP,
                notes=d.notes,
            )
            for d in BIOMARKERS.values()
        ],
        age_hard_range=(AGE_HARD_LOW, AGE_HARD_HIGH),
        age_training_range=(AGE_TRAINING_LOW, AGE_TRAINING_HIGH),
        lod_policy=settings.crp_lod_policy.value,
    )


def _measurements_from_labs(
    db: Session, patient_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[str, RawMeasurement | None]:
    if len(set(ids)) != len(ids):
        raise HTTPException(422, detail={"code": "DUPLICATE_LAB_IDS", "message": "重复的检测记录"})
    labs = db.scalars(select(LabResult).where(LabResult.id.in_(ids))).all()
    if len(labs) != len(ids) or any(lab.patient_id != patient_id for lab in labs):
        raise HTTPException(404, detail={"code": "LAB_NOT_FOUND", "message": "检测记录不存在或不属于该患者"})
    out: dict[str, RawMeasurement | None] = {}
    for lab in labs:
        if lab.biomarker in out:
            raise HTTPException(
                422,
                detail={"code": "DUPLICATE_BIOMARKER", "message": f"指标 {lab.biomarker} 重复"},
            )
        out[lab.biomarker] = RawMeasurement(
            value=lab.value_original,
            unit=lab.unit_original,
            below_lod=lab.below_lod,
            lod=lab.lod_original,
            collected_on=lab.collected_on,
        )
    return out


@router.post(
    "/phenoage",
    response_model=PhenoAgeResponse,
    responses={422: {"model": PhenoAgeRejected}},
    summary="Compute Levine 2018 Clinical PhenoAge (deterministic)",
)
def compute_phenoage(
    body: PhenoAgeRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    principal: Principal = Depends(require(Permission.BIOAGE_COMPUTE)),
):
    rid = request_id(request)
    if (body.biomarkers is None) == (body.lab_result_ids is None):
        raise HTTPException(
            422,
            detail={
                "code": "BAD_REQUEST_SHAPE",
                "message": "必须且只能提供 biomarkers 或 lab_result_ids 之一",
            },
        )

    patient: Patient | None = None
    if body.patient_id is not None:
        if not principal.can(Permission.LAB_WRITE):
            # persisting results against a patient is a clinical write
            raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "无权限为患者保存计算结果"})
        patient = db.get(Patient, body.patient_id)
        if patient is None:
            raise HTTPException(404, detail={"code": "PATIENT_NOT_FOUND", "message": "患者不存在"})

    if body.lab_result_ids is not None:
        if patient is None:
            raise HTTPException(
                422,
                detail={"code": "PATIENT_REQUIRED", "message": "使用 lab_result_ids 时必须提供 patient_id"},
            )
        raw = _measurements_from_labs(db, patient.id, body.lab_result_ids)
    else:
        assert body.biomarkers is not None
        raw = {
            k: RawMeasurement(
                value=v.value,
                unit=v.unit,
                below_lod=v.below_lod,
                lod=v.lod,
                collected_on=v.collected_on,
            )
            for k, v in body.biomarkers.items()
        }

    outcome = run_phenoage(
        raw,
        body.chronological_age,
        lod_policy=settings.crp_lod_policy,
        max_lab_span_days=settings.max_lab_span_days,
    )
    report = outcome.report
    inputs = [MeasurementOut.model_validate(m.as_dict()) for m in report.measurements.values()]

    if not outcome.ok:
        errors = report.errors + outcome.extra_errors
        codes = sorted({e.code for e in errors})
        audit.record(
            db,
            principal,
            "bioage.phenoage.compute",
            "patient" if patient else "adhoc",
            str(patient.id) if patient else None,
            outcome="rejected",
            request_id=rid,
            details={"error_codes": codes},
        )
        db.commit()
        log.info("phenoage rejected", extra={"event": "phenoage_rejected", "error_codes": codes, "request_id": rid})
        rejected = PhenoAgeRejected(
            message="输入未通过校验，未生成 PhenoAge 结果",
            errors=[IssueOut(**e.as_dict()) for e in errors],
            warnings=[IssueOut(**w.as_dict()) for w in report.warnings],
            inputs=inputs,
        )
        return JSONResponse(status_code=422, content=rejected.model_dump(mode="json"))

    out = outcome.output
    assert out is not None and outcome.computed_at is not None and report.age_years is not None
    info = model_info()
    warnings = [IssueOut(**w.as_dict()) for w in report.warnings]
    lab_ids = list(body.lab_result_ids or [])

    result_id = None
    if patient is not None:
        rec = BioAgeResult(
            patient_id=patient.id,
            model_id=info["model_id"],
            model_version=info["model_version"],
            engine_version=info["engine_version"],
            coefficients_sha256=info["coefficients_sha256"],
            algorithm_source=info["algorithm_source"],
            chronological_age=report.age_years,
            phenoage=out.phenoage,
            mortality_score=out.mortality_score,
            linear_predictor=out.linear_predictor,
            lod_policy=settings.crp_lod_policy.value,
            inputs={
                "measurements": [i.model_dump(mode="json") for i in inputs],
                "chronological_age": report.age_years,
            },
            lab_result_ids=[str(i) for i in lab_ids],
            warnings=[w.model_dump() for w in warnings],
            computed_at=outcome.computed_at,
            computed_by=principal.user_id,
        )
        db.add(rec)
        db.flush()
        result_id = rec.id

    audit.record(
        db,
        principal,
        "bioage.phenoage.compute",
        "bioage_result" if result_id else "adhoc",
        str(result_id) if result_id else None,
        request_id=rid,
        details={"model_version": info["model_version"], "warning_codes": sorted({w.code for w in warnings})},
    )
    db.commit()
    log.info(
        "phenoage computed",
        extra={"event": "phenoage_computed", "request_id": rid, "resource_id": str(result_id) if result_id else None},
    )

    return PhenoAgeResponse(
        result_id=result_id,
        patient_id=patient.id if patient else None,
        phenoage=out.phenoage,
        phenoage_rounded=round(out.phenoage, 1),
        chronological_age=report.age_years,
        phenoage_minus_chronological_age=out.phenoage - report.age_years,
        mortality_score=out.mortality_score,
        linear_predictor=out.linear_predictor,
        lod_policy=settings.crp_lod_policy.value,
        computed_at=outcome.computed_at,
        model=ModelInfo(**info),
        inputs=inputs,
        lab_result_ids=lab_ids,
        warnings=warnings,
    )


@router.get("/results/{result_id}", response_model=PhenoAgeResponse)
def get_result(
    result_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.BIOAGE_READ)),
) -> PhenoAgeResponse:
    rec = db.get(BioAgeResult, result_id)
    if rec is None:
        raise HTTPException(404, detail={"code": "RESULT_NOT_FOUND", "message": "结果不存在"})
    audit.record(db, principal, "bioage.result.read", "bioage_result", str(rec.id), request_id=request_id(request))
    db.commit()
    return PhenoAgeResponse(
        result_id=rec.id,
        patient_id=rec.patient_id,
        phenoage=rec.phenoage,
        phenoage_rounded=round(rec.phenoage, 1),
        chronological_age=rec.chronological_age,
        phenoage_minus_chronological_age=rec.phenoage - rec.chronological_age,
        mortality_score=rec.mortality_score,
        linear_predictor=rec.linear_predictor,
        lod_policy=rec.lod_policy,
        computed_at=rec.computed_at,
        model=ModelInfo(
            model_id=rec.model_id,
            model_version=rec.model_version,
            engine_version=rec.engine_version,
            coefficients_sha256=rec.coefficients_sha256,
            algorithm_source=rec.algorithm_source,
        ),
        inputs=[MeasurementOut.model_validate(m) for m in rec.inputs["measurements"]],
        lab_result_ids=[uuid.UUID(i) for i in rec.lab_result_ids],
        warnings=[IssueOut(**w) for w in rec.warnings],
    )
