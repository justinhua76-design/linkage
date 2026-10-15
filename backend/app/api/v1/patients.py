from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import request_id
from app.core.security import Permission, Principal, require
from app.db.models import BioAgeResult, LabResult, Patient
from app.db.session import get_db
from app.domain.biomarkers import BIOMARKERS, BiomarkerCode
from app.domain.units import UnitError, convert, normalise_unit
from app.domain.validation import Issue, QualityStatus, RawMeasurement, validate_measurement
from app.schemas.patients import (
    BioAgeResultSummary,
    LabBatchCreate,
    LabResultOut,
    PatientCreate,
    PatientOut,
    PatientOverview,
)
from app.services import audit

router = APIRouter(prefix="/patients", tags=["patients"])


def _get_patient(db: Session, patient_id: uuid.UUID) -> Patient:
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, detail={"code": "PATIENT_NOT_FOUND", "message": "患者不存在"})
    return p


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    body: PatientCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.PATIENT_CREATE)),
) -> Patient:
    p = Patient(**body.model_dump(), created_by=principal.user_id)
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "PSEUDONYM_EXISTS", "message": "该研究编号已存在"}) from None
    audit.record(db, principal, "patient.create", "patient", str(p.id), request_id=request_id(request))
    db.commit()
    return p


@router.get("", response_model=list[PatientOut])
def list_patients(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.PATIENT_READ)),
) -> list[Patient]:
    rows = list(db.scalars(select(Patient).order_by(Patient.created_at.desc()).limit(200)))
    audit.record(
        db, principal, "patient.list", "patient", None, request_id=request_id(request), details={"count": len(rows)}
    )
    db.commit()
    return rows


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.PATIENT_READ)),
) -> Patient:
    p = _get_patient(db, patient_id)
    audit.record(db, principal, "patient.read", "patient", str(p.id), request_id=request_id(request))
    db.commit()
    return p


def _reference_range(m, code: BiomarkerCode, issues: list[Issue]) -> tuple[float | None, float | None, str | None, str]:
    defn = BIOMARKERS[code]
    if m.reference_low is None and m.reference_high is None:
        return defn.reference_low, defn.reference_high, defn.canonical_unit, "system_default"
    if m.reference_low is None or m.reference_high is None or m.reference_low > m.reference_high:
        issues.append(Issue("REFERENCE_RANGE_INVALID", code.value, "参考范围需同时提供下限和上限，且下限不大于上限"))
        return None, None, None, "lab"
    try:
        unit = normalise_unit(m.reference_unit or m.unit)
        convert(1.0, unit, defn.canonical_unit, defn.conversions)
    except UnitError as e:
        issues.append(Issue(e.code, code.value, f"参考范围单位错误: {e.message}"))
        return None, None, None, "lab"
    return float(m.reference_low), float(m.reference_high), unit, "lab"


@router.post("/{patient_id}/labs", response_model=list[LabResultOut], status_code=201)
def add_labs(
    patient_id: uuid.UUID,
    body: LabBatchCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.LAB_WRITE)),
):
    """Store a batch of manually entered measurements.

    The whole batch is rejected (nothing stored) if any measurement has an
    error-severity issue. Warnings are stored with the row.
    """
    patient = _get_patient(db, patient_id)
    errors: list[Issue] = []
    rows: list[LabResult] = []
    seen: set[str] = set()
    for m in body.measurements:
        if m.biomarker in seen:
            errors.append(Issue("DUPLICATE_BIOMARKER", m.biomarker, "同一批次中指标重复"))
            continue
        seen.add(m.biomarker)
        raw = RawMeasurement(m.value, m.unit, m.below_lod, m.lod, body.collected_on)
        vm, issues = validate_measurement(m.biomarker, raw)
        errs = [i for i in issues if i.severity.value == "error"]
        if errs or vm is None:
            errors.extend(errs)
            continue
        code = BiomarkerCode(m.biomarker)
        r_issues: list[Issue] = []
        ref_low, ref_high, ref_unit, ref_src = _reference_range(m, code, r_issues)
        if r_issues:
            errors.extend(r_issues)
            continue
        status = "below_lod" if vm.quality_status is QualityStatus.BELOW_LOD_IMPUTED else vm.quality_status.value
        rows.append(
            LabResult(
                patient_id=patient.id,
                biomarker=code.value,
                value_original=m.value,
                unit_original=m.unit,
                value_canonical=None if m.below_lod else vm.canonical_value,
                unit_canonical=vm.canonical_unit,
                conversion_factor=vm.conversion_factor,
                below_lod=m.below_lod,
                lod_original=m.lod,
                collected_on=body.collected_on,
                source=body.source,
                source_detail=body.source_detail,
                reference_low=ref_low,
                reference_high=ref_high,
                reference_unit=ref_unit,
                reference_source=ref_src,
                quality_status=status,
                quality_issues=[i.as_dict() for i in issues],
                created_by=principal.user_id,
            )
        )
    if errors:
        audit.record(
            db,
            principal,
            "lab.create",
            "patient",
            str(patient.id),
            outcome="rejected",
            request_id=request_id(request),
            details={"error_codes": sorted({e.code for e in errors})},
        )
        db.commit()
        return JSONResponse(
            status_code=422,
            content={
                "status": "rejected",
                "code": "VALIDATION_FAILED",
                "message": "检测数据未通过校验，未保存任何记录",
                "errors": [e.as_dict() for e in errors],
            },
        )
    db.add_all(rows)
    db.flush()
    audit.record(
        db,
        principal,
        "lab.create",
        "patient",
        str(patient.id),
        request_id=request_id(request),
        details={"count": len(rows)},
    )
    db.commit()
    return [LabResultOut.model_validate(r) for r in rows]


@router.get("/{patient_id}/labs", response_model=list[LabResultOut])
def list_labs(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.LAB_READ)),
) -> list[LabResult]:
    _get_patient(db, patient_id)
    rows = list(
        db.scalars(
            select(LabResult)
            .where(LabResult.patient_id == patient_id)
            .order_by(LabResult.collected_on.desc(), LabResult.created_at.desc())
        )
    )
    audit.record(db, principal, "lab.list", "patient", str(patient_id), request_id=request_id(request))
    db.commit()
    return rows


@router.get("/{patient_id}/overview", response_model=PatientOverview)
def overview(
    patient_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.LAB_READ)),
) -> PatientOverview:
    if not principal.can(Permission.BIOAGE_READ):  # pragma: no cover - all lab readers have it
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "无权限"})
    p = _get_patient(db, patient_id)
    labs = list(
        db.scalars(
            select(LabResult)
            .where(LabResult.patient_id == patient_id)
            .order_by(LabResult.collected_on.desc(), LabResult.created_at.desc())
        )
    )
    latest: dict[str, LabResult] = {}
    for lab in labs:
        latest.setdefault(lab.biomarker, lab)
    results = list(
        db.scalars(
            select(BioAgeResult).where(BioAgeResult.patient_id == patient_id).order_by(BioAgeResult.computed_at.desc())
        )
    )
    audit.record(db, principal, "patient.overview", "patient", str(p.id), request_id=request_id(request))
    db.commit()
    return PatientOverview(
        patient=PatientOut.model_validate(p),
        latest_labs={k: LabResultOut.model_validate(v) for k, v in latest.items()},
        labs=[LabResultOut.model_validate(x) for x in labs],
        results=[BioAgeResultSummary.model_validate(r) for r in results],
    )
