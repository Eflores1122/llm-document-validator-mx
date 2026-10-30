"""Parser and extractor tests, including the no-key path and fakes for vendors."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from docval.config import load_settings
from docval.errors import ExtractionError, MissingCredentialError, ParserError
from docval.extractors import DeterministicExtractor, OpenAIExtractor, build_extractor
from docval.generate import build_cases, write_pdf
from docval.parsers import LlamaParseParser, LocalParser, build_parser
from docval.schemas import (
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    DocType,
    Identificacion,
    ParsedDocument,
)


def test_factories_use_local_backends_without_keys() -> None:
    settings = load_settings()
    assert isinstance(build_parser(settings), LocalParser)
    assert isinstance(build_extractor(settings), DeterministicExtractor)


def test_blank_keys_are_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "")
    settings = load_settings()
    assert settings.openai_api_key is None
    assert settings.llama_cloud_api_key is None
    assert build_parser(settings).backend_name == "local"
    assert build_extractor(settings).backend_name == "deterministic"


def test_factories_select_vendors_only_when_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    settings = load_settings()
    assert build_parser(settings).backend_name == "llamaparse"
    assert build_extractor(settings).backend_name == "openai"
    assert build_parser(settings, "local").backend_name == "local"
    assert build_extractor(settings, "mock").backend_name == "deterministic"


def test_vendor_backends_refuse_without_keys() -> None:
    settings = load_settings()
    with pytest.raises(MissingCredentialError):
        build_parser(settings, "llamaparse")
    with pytest.raises(MissingCredentialError):
        build_extractor(settings, "openai")


def test_local_parser_reads_a_synthetic_pdf(tmp_path: Path) -> None:
    case = build_cases(1, seed=5)[0]
    path = tmp_path / "contrato.pdf"
    write_pdf(path, case.texts[DocType.CONTRATO])
    parsed = LocalParser().parse(path, DocType.CONTRATO)
    assert parsed.backend.startswith("local:")
    assert "CONTRATO LABORAL" in parsed.text
    assert "DOCUMENTO FICTICIO" in parsed.text
    assert "SIN VALIDEZ OFICIAL" in parsed.text
    assert parsed.page_count >= 1
    contract = DeterministicExtractor().extract(parsed)
    assert isinstance(contract, Contrato)
    assert contract.start_date == case.labels.truth.contrato.start_date  # type: ignore[union-attr]
    assert contract.employee_name


def test_deterministic_extractor_reads_both_layouts() -> None:
    cases = build_cases(4, seed=9)
    extractor = DeterministicExtractor()
    for case in cases:
        for doc_type, text in case.texts.items():
            parsed = ParsedDocument(
                source_path=f"mem:{doc_type.value}",
                doc_type=doc_type,
                text=text,
                page_count=1,
                backend="inline",
            )
            model = extractor.extract(parsed)
            truth = getattr(case.labels.truth, doc_type.value)
            if doc_type is DocType.IDENTIFICACION:
                assert isinstance(model, Identificacion)
                assert model.birth_date == truth.birth_date
                assert model.curp == truth.curp
            elif doc_type is DocType.CONSTANCIA_FISCAL:
                assert isinstance(model, ConstanciaFiscal)
                assert model.rfc == truth.rfc
                assert model.issue_date == truth.issue_date
                assert model.tax_status == truth.tax_status
            elif doc_type is DocType.COMPROBANTE_DOMICILIO:
                assert isinstance(model, ComprobanteDomicilio)
                assert model.issue_date == truth.issue_date
                assert model.postal_code == truth.postal_code
            else:
                assert isinstance(model, Contrato)
                assert model.start_date == truth.start_date
                assert model.signed_date == truth.signed_date
                assert model.contract_kind == truth.contract_kind


class _FakeTransport:
    def __init__(self, text: str) -> None:
        self.text = text
        self.posts: list[str] = []
        self.gets = 0

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        data_fields: dict[str, str],
        file_field: tuple[str, str, bytes],
    ) -> dict[str, object]:
        self.posts.append(url)
        assert headers["Authorization"].startswith("Bearer ")
        assert "tier" in data_fields["configuration"]
        assert file_field[2]
        return {"id": "job_123", "status": "PENDING"}

    def get_json(self, url: str, headers: dict[str, str]) -> dict[str, object]:
        self.gets += 1
        if self.gets == 1:
            return {"job": {"id": "job_123", "status": "RUNNING"}}
        return {"job": {"id": "job_123", "status": "COMPLETED"}, "text_full": self.text}


def test_llamaparse_polls_until_text(tmp_path: Path) -> None:
    path = tmp_path / "contrato.pdf"
    path.write_bytes(b"%PDF-1.4 synthetic")
    transport = _FakeTransport("CONTRATO LABORAL\nTrabajador: Ana Lopez")
    parser = LlamaParseParser(
        "test-key",
        transport=transport,
        sleep=lambda _seconds: None,
        timeout_s=5,
    )
    parsed = parser.parse(path, DocType.CONTRATO)
    assert parsed.backend == "llamaparse"
    assert "Ana Lopez" in parsed.text
    assert transport.posts[0].endswith("/api/v2/parse/upload")
    assert transport.gets == 2


def test_llamaparse_reports_failed_jobs(tmp_path: Path) -> None:
    path = tmp_path / "contrato.pdf"
    path.write_bytes(b"%PDF")

    class Failed(_FakeTransport):
        def get_json(self, url: str, headers: dict[str, str]) -> dict[str, object]:
            return {"job": {"id": "job_123", "status": "FAILED", "error_message": "bad pdf"}}

    parser = LlamaParseParser(
        "test-key", transport=Failed("unused"), sleep=lambda _s: None, timeout_s=5
    )
    with pytest.raises(ParserError, match="bad pdf"):
        parser.parse(path, DocType.CONTRATO)


def test_openai_extractor_uses_structured_schema() -> None:
    captured: dict[str, object] = {}

    def parse(**kwargs: object) -> object:
        captured.update(kwargs)
        schema = kwargs["response_format"]
        model = Contrato(
            employee_name="Ana Lopez",
            start_date=date(2026, 10, 1),
            signed_date=date(2026, 9, 28),
        )
        assert schema is Contrato
        message = SimpleNamespace(parsed=model, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        beta=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    )
    extractor = OpenAIExtractor(model="gpt-4o-mini", client=client)
    parsed = ParsedDocument(
        source_path="inline:contrato",
        doc_type=DocType.CONTRATO,
        text="CONTRATO LABORAL\nFecha de inicio: 2026-10-01",
        page_count=1,
        backend="inline",
    )
    result = extractor.extract(parsed)
    assert isinstance(result, Contrato)
    assert result.employee_name == "Ana Lopez"
    assert captured["model"] == "gpt-4o-mini"


def test_openai_extractor_raises_on_refusal() -> None:
    def parse(**_kwargs: object) -> object:
        message = SimpleNamespace(parsed=None, refusal="refused")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        beta=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    )
    extractor = OpenAIExtractor(model="gpt-4o-mini", client=client)
    parsed = ParsedDocument(
        source_path="inline:contrato",
        doc_type=DocType.CONTRATO,
        text="CONTRATO LABORAL",
        page_count=1,
        backend="inline",
    )
    with pytest.raises(ExtractionError, match="refused"):
        extractor.extract(parsed)
