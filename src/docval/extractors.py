"""Field extraction.

The deterministic extractor reads the labeled synthetic layouts with no network
calls. `OpenAIExtractor` uses structured outputs when `OPENAI_API_KEY` is set.
"""

from __future__ import annotations

from typing import Protocol

from docval.config import Settings
from docval.errors import ExtractionError, MissingCredentialError
from docval.schemas import (
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    DocType,
    DocumentModel,
    Identificacion,
    ParsedDocument,
)
from docval.textutil import find_labeled, normalize_id, parse_iso_date

_OPENAI_SYSTEM = (
    "You extract structured fields from one synthetic Mexican onboarding document "
    "for a fictitious staffing company. The document is fictional. Copy values that "
    "are printed; use null when a field is absent. Do not invent identifiers. "
    "Dates must be ISO dates (YYYY-MM-DD)."
)

_MODEL_FOR: dict[DocType, type[DocumentModel]] = {
    DocType.IDENTIFICACION: Identificacion,
    DocType.CONSTANCIA_FISCAL: ConstanciaFiscal,
    DocType.COMPROBANTE_DOMICILIO: ComprobanteDomicilio,
    DocType.CONTRATO: Contrato,
}

_ID_LABELS = ["RFC", "R.F.C.", "R.F.C"]
_CURP_LABELS = ["CURP", "Clave CURP"]


class DocumentExtractor(Protocol):
    backend_name: str

    def extract(self, parsed: ParsedDocument) -> DocumentModel:
        """Turn parsed text into the schema for that document type."""


class DeterministicExtractor:
    """Rule-based extractor for the two synthetic layouts this repo generates."""

    backend_name = "deterministic"

    def extract(self, parsed: ParsedDocument) -> DocumentModel:
        if not parsed.text.strip():
            raise ExtractionError(f"{parsed.doc_type.value} text is empty")
        if parsed.doc_type is DocType.IDENTIFICACION:
            return _identificacion(parsed.text)
        if parsed.doc_type is DocType.CONSTANCIA_FISCAL:
            return _constancia(parsed.text)
        if parsed.doc_type is DocType.COMPROBANTE_DOMICILIO:
            return _comprobante(parsed.text)
        if parsed.doc_type is DocType.CONTRATO:
            return _contrato(parsed.text)
        raise ExtractionError(f"unsupported document type {parsed.doc_type}")


def _identificacion(text: str) -> Identificacion:
    return Identificacion(
        full_name=find_labeled(text, ["Nombre completo", "Nombre"]),
        rfc=normalize_id(find_labeled(text, _ID_LABELS)),
        curp=normalize_id(find_labeled(text, _CURP_LABELS)),
        birth_date=parse_iso_date(find_labeled(text, ["Fecha de nacimiento", "Nacimiento"])),
        address=find_labeled(text, ["Domicilio"]),
        sex=find_labeled(text, ["Sexo"]),
    )


def _constancia(text: str) -> ConstanciaFiscal:
    issued = find_labeled(text, ["Fecha de emision", "Fecha de emisión", "Emitida"])
    return ConstanciaFiscal(
        holder_name=find_labeled(text, ["Nombre", "Contribuyente"]),
        rfc=normalize_id(find_labeled(text, _ID_LABELS)),
        curp=normalize_id(find_labeled(text, _CURP_LABELS)),
        postal_code=find_labeled(text, ["Codigo postal fiscal", "C.P. fiscal"]),
        issue_date=parse_iso_date(issued),
        tax_status=find_labeled(text, ["Estatus", "Situacion", "Situación"]),
    )


def _comprobante(text: str) -> ComprobanteDomicilio:
    issued = find_labeled(text, ["Fecha de emision", "Fecha de emisión"])
    return ComprobanteDomicilio(
        holder_name=find_labeled(text, ["Nombre", "Cliente"]),
        street=find_labeled(text, ["Calle"]),
        neighborhood=find_labeled(text, ["Colonia"]),
        city=find_labeled(text, ["Ciudad"]),
        state=find_labeled(text, ["Estado"]),
        postal_code=find_labeled(text, ["Codigo postal", "Código postal", "C.P."]),
        issue_date=parse_iso_date(issued),
        issuer=find_labeled(text, ["Emisor"]),
    )


def _contrato(text: str) -> Contrato:
    return Contrato(
        employee_name=find_labeled(text, ["Trabajador", "Candidato"]),
        rfc=normalize_id(find_labeled(text, _ID_LABELS)),
        curp=normalize_id(find_labeled(text, _CURP_LABELS)),
        employer=find_labeled(text, ["Empleador", "Empresa"]),
        role=find_labeled(text, ["Puesto", "Puesto ofrecido"]),
        signed_date=parse_iso_date(find_labeled(text, ["Fecha de firma"])),
        start_date=parse_iso_date(find_labeled(text, ["Fecha de inicio", "Fecha de ingreso"])),
        contract_kind=find_labeled(text, ["Tipo", "Documento"]),
    )


class OpenAIExtractor:
    """Structured extraction via the OpenAI SDK. The SDK is imported on first use."""

    backend_name = "openai"

    def __init__(
        self, model: str, *, api_key: str | None = None, client: object | None = None
    ) -> None:
        if client is None and (api_key is None or not api_key.strip()):
            raise MissingCredentialError("OPENAI_API_KEY is not set")
        self.model = model
        self._api_key = api_key
        self._client = client

    def extract(self, parsed: ParsedDocument) -> DocumentModel:
        if not parsed.text.strip():
            raise ExtractionError(f"{parsed.doc_type.value} text is empty")
        schema = _MODEL_FOR[parsed.doc_type]
        client = self._resolve_client()
        try:
            completion = client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": _OPENAI_SYSTEM},
                    {
                        "role": "user",
                        "content": (f"Document type: {parsed.doc_type.value}\n\n{parsed.text}"),
                    },
                ],
                response_format=schema,
            )
        except Exception as exc:  # noqa: BLE001 - vendor SDK raises many types
            raise ExtractionError(f"OpenAI extraction failed: {exc}") from exc
        message = completion.choices[0].message
        parsed_model = getattr(message, "parsed", None)
        if parsed_model is None:
            refusal = getattr(message, "refusal", None)
            raise ExtractionError(refusal or "model returned no structured result")
        if not isinstance(parsed_model, schema):
            raise ExtractionError(
                f"model returned {type(parsed_model).__name__}, expected {schema.__name__}"
            )
        return parsed_model

    def _resolve_client(self) -> object:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise MissingCredentialError(
                "openai is not installed. Install docval[llm] to use the OpenAI extractor."
            ) from exc
        self._client = OpenAI(api_key=self._api_key)
        return self._client


def build_extractor(settings: Settings, prefer: str | None = None) -> DocumentExtractor:
    """Select an extractor. The default is OpenAI only when a key is configured."""
    choice = (prefer or "").strip().lower()
    if choice in {"", "auto"}:
        choice = "openai" if settings.openai_api_key else "deterministic"
    if choice in {"mock", "deterministic"}:
        return DeterministicExtractor()
    if choice == "openai":
        if not settings.openai_api_key:
            raise MissingCredentialError(
                "OPENAI_API_KEY is not set; use --extractor deterministic or unset --extractor"
            )
        return OpenAIExtractor(settings.openai_model, api_key=settings.openai_api_key)
    raise ExtractionError(f"unknown extractor '{prefer}'. Expected deterministic, mock, or openai.")
