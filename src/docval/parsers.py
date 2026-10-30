"""Pluggable document parsers.

`LocalParser` reads digital PDFs with pdfplumber, falling back to pypdf.
`LlamaParseParser` calls the LlamaCloud parse API when `LLAMA_CLOUD_API_KEY`
is set. The factory never selects it without a key.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Protocol

from docval.config import Settings
from docval.errors import MissingCredentialError, ParserError
from docval.schemas import DocType, ParsedDocument

_FILENAME_TYPES = {
    "identificacion.pdf": DocType.IDENTIFICACION,
    "constancia_fiscal.pdf": DocType.CONSTANCIA_FISCAL,
    "comprobante_domicilio.pdf": DocType.COMPROBANTE_DOMICILIO,
    "contrato.pdf": DocType.CONTRATO,
}


def detect_doc_type(text: str, filename: str | None = None) -> DocType:
    if filename:
        stem = Path(filename).name.lower()
        if stem in _FILENAME_TYPES:
            return _FILENAME_TYPES[stem]
    lowered = text.lower()
    if "constancia de situacion fiscal" in lowered or "constancia de situación fiscal" in lowered:
        return DocType.CONSTANCIA_FISCAL
    if "contrato laboral" in lowered or "carta oferta" in lowered:
        return DocType.CONTRATO
    if "comprobante de domicilio" in lowered:
        return DocType.COMPROBANTE_DOMICILIO
    if (
        "resumen de identificacion" in lowered
        or "resumen de identificación" in lowered
        or "constancia de identificacion" in lowered
        or "constancia de identificación" in lowered
    ):
        return DocType.IDENTIFICACION
    raise ParserError("could not detect document type from filename or text")


class DocumentParser(Protocol):
    backend_name: str

    def parse(self, path: Path, doc_type: DocType | None = None) -> ParsedDocument:
        """Read one document into text."""


class LocalParser:
    """Free parser. Prefers pdfplumber and falls back to pypdf."""

    def __init__(self) -> None:
        self.backend_name = "local"

    def parse(self, path: Path, doc_type: DocType | None = None) -> ParsedDocument:
        if not path.is_file():
            raise ParserError(f"file not found: {path}")
        text, pages, engine = _read_pdf(path)
        if not text.strip():
            raise ParserError(f"no text extracted from {path.name}")
        resolved = doc_type or detect_doc_type(text, path.name)
        return ParsedDocument(
            source_path=str(path),
            doc_type=resolved,
            text=text,
            page_count=pages,
            backend=f"local:{engine}",
        )


def _read_pdf(path: Path) -> tuple[str, int, str]:
    pdfplumber_error: Exception | None = None
    try:
        import pdfplumber
    except ImportError as exc:
        pdfplumber_error = exc
    else:
        with pdfplumber.open(path) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages]
        text = "\n".join(pages).strip()
        if text:
            return text, len(pages), "pdfplumber"
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        if pdfplumber_error is not None:
            raise ParserError("neither pdfplumber nor pypdf could be imported") from exc
        raise ParserError("pypdf is not installed") from exc
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages).strip(), len(pages), "pypdf"


class HttpTransport(Protocol):
    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        data_fields: dict[str, str],
        file_field: tuple[str, str, bytes],
    ) -> dict[str, object]:
        """POST a multipart form. file_field is (filename, content_type, content)."""

    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, object]:
        """GET a JSON document."""


class UrllibTransport:
    """Stdlib transport so the LlamaParse backend adds no required dependency."""

    def __init__(self, timeout_s: float = 60.0) -> None:
        self.timeout_s = timeout_s

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        data_fields: dict[str, str],
        file_field: tuple[str, str, bytes],
    ) -> dict[str, object]:
        body, content_type = _encode_multipart(data_fields, file_field)
        request_headers = dict(headers)
        request_headers["Content-Type"] = content_type
        return _request_json(url, request_headers, body, self.timeout_s, method="POST")

    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, object]:
        return _request_json(url, headers, None, self.timeout_s, method="GET")


def _encode_multipart(
    fields: dict[str, str],
    file_field: tuple[str, str, bytes],
) -> tuple[bytes, str]:
    filename, content_type, content = file_field
    boundary = f"----docval{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        + content
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _request_json(
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout_s: float,
    *,
    method: str,
) -> dict[str, object]:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ParserError(f"LlamaParse HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ParserError(f"LlamaParse request failed: {exc.reason}") from exc
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ParserError("LlamaParse returned non-JSON") from exc
    if not isinstance(parsed, dict):
        raise ParserError("LlamaParse returned an unexpected payload")
    return parsed


class LlamaParseParser:
    """LlamaCloud parse API client (POST /api/v2/parse/upload, then poll)."""

    backend_name = "llamaparse"

    def __init__(
        self,
        api_key: str,
        *,
        tier: str = "fast",
        base_url: str = "https://api.cloud.llamaindex.ai",
        timeout_s: float = 120.0,
        poll_interval_s: float = 2.0,
        transport: HttpTransport | None = None,
        sleep: object | None = None,
    ) -> None:
        if not api_key.strip():
            raise MissingCredentialError("LLAMA_CLOUD_API_KEY is not set")
        self._api_key = api_key.strip()
        self._tier = tier
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._poll_interval_s = poll_interval_s
        self._transport = transport or UrllibTransport(timeout_s=min(60.0, timeout_s))
        self._sleep = time.sleep if sleep is None else sleep

    def parse(self, path: Path, doc_type: DocType | None = None) -> ParsedDocument:
        if not path.is_file():
            raise ParserError(f"file not found: {path}")
        job_id = self._upload(path)
        text = self._poll(job_id)
        resolved = doc_type or detect_doc_type(text, path.name)
        return ParsedDocument(
            source_path=str(path),
            doc_type=resolved,
            text=text,
            page_count=max(1, text.count("\f") + 1),
            backend=self.backend_name,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "docval/0.1.0",
        }

    def _upload(self, path: Path) -> str:
        configuration = json.dumps({"tier": self._tier, "version": "latest"})
        payload = self._transport.post_multipart(
            f"{self._base_url}/api/v2/parse/upload",
            self._headers(),
            {"configuration": configuration},
            (path.name, "application/pdf", path.read_bytes()),
        )
        job_id = payload.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise ParserError("LlamaParse upload did not return a job id")
        return job_id

    def _poll(self, job_id: str) -> str:
        deadline = time.monotonic() + self._timeout_s
        url = f"{self._base_url}/api/v2/parse/{job_id}?expand=text_full"
        while True:
            payload = self._transport.get_json(url, self._headers())
            job = payload.get("job")
            status_source = job if isinstance(job, dict) else payload
            status = str(status_source.get("status", "")).upper()
            if status == "COMPLETED":
                text = _text_from_payload(payload)
                if not text.strip():
                    raise ParserError("LlamaParse completed without document text")
                return text
            if status in {"FAILED", "CANCELLED"}:
                message = status_source.get("error_message") or status
                raise ParserError(f"LlamaParse job {status}: {message}")
            if time.monotonic() > deadline:
                raise ParserError(f"LlamaParse job {job_id} timed out")
            self._sleep(self._poll_interval_s)  # type: ignore[operator]


def _text_from_payload(payload: dict[str, object]) -> str:
    full = payload.get("text_full")
    if isinstance(full, str) and full.strip():
        return full
    text_obj = payload.get("text")
    if isinstance(text_obj, dict):
        pages = text_obj.get("pages") or []
        if isinstance(pages, list):
            parts: list[str] = []
            for page in pages:
                if isinstance(page, dict):
                    parts.append(str(page.get("text") or ""))
            joined = "\n".join(parts).strip()
            if joined:
                return joined
    markdown = payload.get("markdown_full")
    if isinstance(markdown, str):
        return markdown
    return ""


def build_parser(settings: Settings, prefer: str | None = None) -> DocumentParser:
    """Select a parser. The default is LlamaParse only when a key is configured."""
    choice = (prefer or "").strip().lower()
    if choice in {"", "auto"}:
        choice = "llamaparse" if settings.llama_cloud_api_key else "local"
    if choice == "local":
        return LocalParser()
    if choice == "llamaparse":
        if not settings.llama_cloud_api_key:
            raise MissingCredentialError(
                "LLAMA_CLOUD_API_KEY is not set; use --parser local or unset --parser"
            )
        return LlamaParseParser(
            settings.llama_cloud_api_key,
            tier=settings.llama_parse_tier,
            base_url=settings.llama_cloud_base_url,
            timeout_s=settings.llama_parse_timeout_s,
        )
    raise ParserError(f"unknown parser '{prefer}'. Expected local or llamaparse.")
