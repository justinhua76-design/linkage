"""BHRT prescription-draft endpoints (stateless; nothing clinical is stored)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import request_id
from app.core.security import Permission, Principal, require
from app.db.session import get_db
from app.domain.bhrt import rules as R
from app.domain.bhrt.engine import ENGINE_VERSION, evaluate
from app.domain.bhrt.intake import BhrtIntake
from app.domain.bhrt.labs import ANALYTES
from app.domain.bhrt.products import CLICK_MG_CREAM, CLICKS_PER_CONTAINER, PRODUCTS
from app.domain.bhrt.report_parser import PdfError, parse_text, pdf_text
from app.services import audit

router = APIRouter(prefix="/bhrt", tags=["bhrt"])


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, max_length=200_000)
    pdf_base64: str | None = Field(default=None, max_length=14_000_000)


@router.get("/catalog")
def catalog(_: Principal = Depends(require(Permission.BHRT_DRAFT))) -> dict:
    return {
        "engine_version": ENGINE_VERSION,
        "click_mg_cream": CLICK_MG_CREAM,
        "clicks_per_container": CLICKS_PER_CONTAINER,
        "products": [asdict(p) for p in PRODUCTS.values()],
        "analytes": [
            {
                "code": a.code,
                "name_zh": a.name_zh,
                "canonical_unit": a.canonical_unit,
                "units": list(a.units),
                "group": a.group,
            }
            for a in ANALYTES.values()
        ],
        "mrs_items": list(R.MRS_ITEMS),
        "adam_items": list(R.ADAM_ITEMS),
    }


@router.post("/reports/parse")
def parse_report(
    body: ParseRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.BHRT_DRAFT)),
) -> dict:
    if (body.text is None) == (body.pdf_base64 is None):
        raise HTTPException(422, detail={"code": "BAD_REQUEST_SHAPE", "message": "必须且只能提供 text 或 pdf_base64"})
    if body.pdf_base64 is not None:
        try:
            text = pdf_text(body.pdf_base64)
        except PdfError as e:
            raise HTTPException(422, detail={"code": "PDF_INVALID", "message": str(e)}) from e
        if len(text.strip()) < 20:
            raise HTTPException(
                422,
                detail={"code": "PDF_NO_TEXT", "message": "PDF 没有文字层（可能是扫描件），请粘贴文字或先 OCR"},
            )
    else:
        text = body.text or ""
    result = parse_text(text)
    audit.record(
        db,
        principal,
        "bhrt.report.parse",
        "adhoc",
        None,
        request_id=request_id(request),
        details={"extracted_count": len(result.labs)},
    )
    db.commit()
    return result.as_dict()


@router.post("/evaluate")
def evaluate_intake(
    body: BhrtIntake,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require(Permission.BHRT_DRAFT)),
) -> dict:
    result = evaluate(body)
    audit.record(
        db,
        principal,
        "bhrt.evaluate",
        "adhoc",
        None,
        request_id=request_id(request),
        details={"status": result.status, "gate": result.gate, "engine_version": ENGINE_VERSION},
    )
    db.commit()
    return result.as_dict()
