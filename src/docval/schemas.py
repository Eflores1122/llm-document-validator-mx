"""Pydantic contracts shared by generation, extraction, and reports."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DocType(StrEnum):
    IDENTIFICACION = "identificacion"
    CONSTANCIA_FISCAL = "constancia_fiscal"
    COMPROBANTE_DOMICILIO = "comprobante_domicilio"
    CONTRATO = "contrato"


DOC_FILENAMES: dict[DocType, str] = {
    DocType.IDENTIFICACION: "identificacion.pdf",
    DocType.CONSTANCIA_FISCAL: "constancia_fiscal.pdf",
    DocType.COMPROBANTE_DOMICILIO: "comprobante_domicilio.pdf",
    DocType.CONTRATO: "contrato.pdf",
}


class Application(BaseModel):
    """Hire-record facts captured when the expediente is opened. Pipeline inputs."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    hire_date: date
    full_name: str
    rfc: str
    curp: str
    address: str
    agreed_start: date


class Identificacion(BaseModel):
    """Structured identification summary. This is not an official credential."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    rfc: str | None = None
    curp: str | None = None
    birth_date: date | None = None
    address: str | None = None
    sex: str | None = None


class ConstanciaFiscal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holder_name: str | None = None
    rfc: str | None = None
    curp: str | None = None
    postal_code: str | None = None
    issue_date: date | None = None
    tax_status: str | None = None


class ComprobanteDomicilio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holder_name: str | None = None
    street: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    issue_date: date | None = None
    issuer: str | None = None


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_name: str | None = None
    rfc: str | None = None
    curp: str | None = None
    employer: str | None = None
    role: str | None = None
    signed_date: date | None = None
    start_date: date | None = None
    contract_kind: str | None = None


class ExtractedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identificacion: Identificacion | None = None
    constancia_fiscal: ConstanciaFiscal | None = None
    comprobante_domicilio: ComprobanteDomicilio | None = None
    contrato: Contrato | None = None


DocumentModel = Identificacion | ConstanciaFiscal | ComprobanteDomicilio | Contrato


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str
    doc_type: DocType
    text: str
    page_count: int
    backend: str


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    passed: bool
    reason: str


class ParsedRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: DocType
    source_path: str
    page_count: int
    backend: str


class FileReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    case_id: str
    overall_passed: bool
    parser_backend: str
    extractor_backend: str
    elapsed_ms: float
    application: Application
    documents: list[ParsedRef]
    extracted: ExtractedFile
    rules: list[RuleResult]
    warnings: list[str] = Field(default_factory=list)


class RuleExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    reason: str


class Labels(BaseModel):
    """Eval-only ground truth. The run command does not read this file."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    defects: list[str]
    notes: list[str]
    truth: ExtractedFile
    expected_rules: dict[str, RuleExpectation]


class InlineDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: DocType
    text: str


class ValidateTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application: Application
    documents: list[InlineDocument]
