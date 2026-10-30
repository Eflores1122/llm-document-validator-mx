"""Parse, extract, and review one onboarding expediente."""

from __future__ import annotations

import json
import time
from pathlib import Path

from docval.config import Settings, load_settings
from docval.errors import DocvalError, ExtractionError
from docval.extractors import DocumentExtractor, build_extractor
from docval.parsers import DocumentParser, build_parser
from docval.rules import run_rules
from docval.schemas import (
    DOC_FILENAMES,
    Application,
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    DocType,
    ExtractedFile,
    FileReport,
    Identificacion,
    InlineDocument,
    ParsedDocument,
    ParsedRef,
    ValidateTextRequest,
)

_BANNER = "SIN VALIDEZ OFICIAL"


def validate_case_dir(
    case_dir: Path,
    *,
    settings: Settings | None = None,
    parser: DocumentParser | None = None,
    extractor: DocumentExtractor | None = None,
    parser_name: str | None = None,
    extractor_name: str | None = None,
) -> FileReport:
    """Validate one case folder that contains application.json and four PDFs."""
    settings = settings or load_settings()
    application_path = case_dir / "application.json"
    if not application_path.is_file():
        raise DocvalError(f"missing application.json in {case_dir}")
    application = Application.model_validate(
        json.loads(application_path.read_text(encoding="utf-8"))
    )
    parser = parser or build_parser(settings, parser_name)
    extractor = extractor or build_extractor(settings, extractor_name)
    parsed: list[ParsedDocument] = []
    for doc_type, filename in DOC_FILENAMES.items():
        path = case_dir / filename
        parsed.append(parser.parse(path, doc_type))
    return _assemble(application, parsed, extractor, settings, parser_backend=_backend_name(parsed))


def validate_texts(
    request: ValidateTextRequest,
    *,
    settings: Settings | None = None,
    extractor: DocumentExtractor | None = None,
) -> FileReport:
    """Validate documents that are already text. Used by the HTTP API and tests."""
    settings = settings or load_settings()
    extractor = extractor or build_extractor(settings)
    parsed = [_inline(document) for document in request.documents]
    return _assemble(request.application, parsed, extractor, settings, parser_backend="inline")


def _inline(document: InlineDocument) -> ParsedDocument:
    return ParsedDocument(
        source_path=f"inline:{document.doc_type.value}",
        doc_type=document.doc_type,
        text=document.text,
        page_count=1,
        backend="inline",
    )


def _assemble(
    application: Application,
    parsed: list[ParsedDocument],
    extractor: DocumentExtractor,
    settings: Settings,
    *,
    parser_backend: str,
) -> FileReport:
    started = time.perf_counter()
    extracted, warnings = _extract_all(parsed, extractor)
    rules = run_rules(application, extracted, settings)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return FileReport(
        case_id=application.case_id,
        overall_passed=all(rule.passed for rule in rules),
        parser_backend=parser_backend,
        extractor_backend=extractor.backend_name,
        elapsed_ms=elapsed_ms,
        application=application,
        documents=[
            ParsedRef(
                doc_type=document.doc_type,
                source_path=document.source_path,
                page_count=document.page_count,
                backend=document.backend,
            )
            for document in parsed
        ],
        extracted=extracted,
        rules=rules,
        warnings=warnings,
    )


def _extract_all(
    parsed: list[ParsedDocument],
    extractor: DocumentExtractor,
) -> tuple[ExtractedFile, list[str]]:
    extracted = ExtractedFile()
    warnings: list[str] = []
    seen: set[DocType] = set()
    for document in parsed:
        if _BANNER not in document.text and "SYNTHETIC FIXTURE" not in document.text:
            warnings.append(f"{document.doc_type.value} is missing the synthetic-fixture banner")
        seen.add(document.doc_type)
        try:
            model = extractor.extract(document)
        except ExtractionError as exc:
            warnings.append(f"{document.doc_type.value}: {exc}")
            continue
        _assign(extracted, document.doc_type, model, warnings)
    missing = [doc_type.value for doc_type in DOC_FILENAMES if doc_type not in seen]
    if missing:
        warnings.append("missing documents: " + ", ".join(missing))
    return extracted, warnings


def _assign(
    extracted: ExtractedFile,
    doc_type: DocType,
    model: object,
    warnings: list[str],
) -> None:
    if doc_type is DocType.IDENTIFICACION and isinstance(model, Identificacion):
        extracted.identificacion = model
    elif doc_type is DocType.CONSTANCIA_FISCAL and isinstance(model, ConstanciaFiscal):
        extracted.constancia_fiscal = model
    elif doc_type is DocType.COMPROBANTE_DOMICILIO and isinstance(model, ComprobanteDomicilio):
        extracted.comprobante_domicilio = model
    elif doc_type is DocType.CONTRATO and isinstance(model, Contrato):
        extracted.contrato = model
    else:
        warnings.append(f"{doc_type.value}: extractor returned {type(model).__name__}")


def _backend_name(parsed: list[ParsedDocument]) -> str:
    names: list[str] = []
    for document in parsed:
        if document.backend not in names:
            names.append(document.backend)
    return ",".join(names) if names else "none"


def iter_case_dirs(path: Path) -> list[Path]:
    """Accept a case directory, a generated dataset root, or a folder of cases."""
    if (path / "application.json").is_file():
        return [path]
    if (path / "manifest.json").is_file():
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        case_ids = manifest.get("cases")
        if not isinstance(case_ids, list) or not case_ids:
            raise DocvalError(f"{path / 'manifest.json'} has no cases")
        return [path / "cases" / str(case_id) for case_id in case_ids]
    if path.is_dir():
        found = sorted(item for item in path.iterdir() if (item / "application.json").is_file())
        if found:
            return found
    raise DocvalError(
        f"{path} is not a case directory or dataset root "
        "(expected application.json or manifest.json)"
    )
