"""Small HTTP API for text validation and golden-case replay."""

from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from docval import __version__
from docval.config import load_settings
from docval.errors import DocvalError
from docval.extractors import build_extractor
from docval.parsers import build_parser
from docval.pipeline import validate_case_dir, validate_texts
from docval.rules import RULE_DESCRIPTIONS, RULE_IDS
from docval.schemas import FileReport, ValidateTextRequest

app = FastAPI(
    title="docval",
    version=__version__,
    summary="Validate synthetic employee-onboarding files.",
)

_CASE_ID = re.compile(r"^EXP-\d{4}$")


@app.exception_handler(DocvalError)
def _docval_error(_request: object, exc: DocvalError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    settings = load_settings()
    return {
        "status": "ok",
        "version": __version__,
        "parser_backend": build_parser(settings).backend_name,
        "extractor_backend": build_extractor(settings).backend_name,
    }


@app.get("/rules")
def rules() -> list[dict[str, str]]:
    return [{"id": rule_id, "description": RULE_DESCRIPTIONS[rule_id]} for rule_id in RULE_IDS]


@app.post("/validate", response_model=FileReport)
def validate(body: ValidateTextRequest) -> FileReport:
    """Validate a hire record plus document texts. No files are read."""
    return validate_texts(body)


@app.post("/cases/{case_id}/validate", response_model=FileReport)
def validate_saved_case(case_id: str) -> FileReport:
    """Replay one case from DOCVAL_GOLDEN_ROOT (default data/golden)."""
    if _CASE_ID.fullmatch(case_id) is None:
        raise HTTPException(status_code=400, detail="case id must look like EXP-0001")
    root = Path(os.environ.get("DOCVAL_GOLDEN_ROOT", "data/golden")).resolve()
    case_dir = (root / "cases" / case_id).resolve()
    if not case_dir.is_relative_to(root):
        raise HTTPException(status_code=400, detail="invalid case path")
    if not case_dir.is_dir():
        raise HTTPException(status_code=404, detail="case not found")
    return validate_case_dir(case_dir)
