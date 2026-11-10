"""Build site/data/site.json from the golden files and the Python rules.

The browser port in site/engine.js is checked against this file. Numbers in
the page's measurement table come from reports/eval/report.json, not from
hand-typed copy.
"""

from __future__ import annotations

import json
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from docval.config import Settings
from docval.extractors import DeterministicExtractor
from docval.pipeline import validate_texts
from docval.rules import run_rules
from docval.schemas import (
    Application,
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    DocType,
    ExtractedFile,
    Identificacion,
    InlineDocument,
    Labels,
    ValidateTextRequest,
)
from docval.textutil import names_match

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"
EVAL_REPORT = ROOT / "reports" / "eval" / "report.json"
OUT = ROOT / "site" / "data" / "site.json"

DOC_FILES = {
    DocType.IDENTIFICACION: "identificacion.txt",
    DocType.CONSTANCIA_FISCAL: "constancia_fiscal.txt",
    DocType.COMPROBANTE_DOMICILIO: "comprobante_domicilio.txt",
    DocType.CONTRATO: "contrato.txt",
}

NAME_PAIRS: tuple[tuple[str | None, str | None], ...] = (
    ("María Fernanda Núñez García", "Maria Fernanda Nunez Garcia"),
    ("Núñez García, María Fernanda", "María Fernanda Núñez García"),
    ("María F Núñez García", "María Fernanda Núñez García"),
    ("María del Carmen Ruiz", "Maria Carmen Ruiz"),
    ("María de las Nieves Sol", "Maria Nieves Sol"),
    ("María Fernanda", "Maria Fernada"),
    ("María Fernanda", "Maria Fernando"),
    ("Ana López", "Ana López Díaz"),
    ("María Fernanda Núñez García", "Juan Carlos Pérez López"),
    ("Ana", "A"),
    (None, "Ana"),
    ("", "Ana"),
)

RATIO_PAIRS: tuple[tuple[str, str], ...] = (
    ("FERNANDA", "FERNADA"),
    ("FERNANDA", "FERNANDO"),
    ("HERNANDEZ", "HERNANDES"),
    ("abcd", "bcde"),
    ("abxcd", "abcd"),
    ("private Thread currentThread;", "private volatile Thread currentThread;"),
    ("a" * 180 + "bcdefghijXYZ", "a" * 150 + "bcdefghijXYZ" + "a" * 40),
    ("Z" * 220 + "que", "Z" * 220 + "qui"),
)


def _application(**overrides: object) -> Application:
    payload: dict[str, object] = {
        "case_id": "EXP-0001",
        "hire_date": date(2026, 10, 1),
        "full_name": "María Fernanda Núñez García",
        "rfc": "NUGA900101AB1",
        "curp": "NUGA900101MJCZNR09",
        "address": "Av. Palma 128",
        "agreed_start": date(2026, 10, 1),
    }
    payload.update(overrides)
    return Application.model_validate(payload)


def _extracted() -> ExtractedFile:
    return ExtractedFile(
        identificacion=Identificacion(
            full_name="NUNEZ GARCIA, MARIA FERNANDA",
            rfc="NUGA900101AB1",
            curp="NUGA900101MJCZNR09",
        ),
        constancia_fiscal=ConstanciaFiscal(
            holder_name="Maria Fernanda Nunez Garcia",
            rfc="NUGA-900101-AB1",
            curp="NUGA900101MJCZNR09",
        ),
        comprobante_domicilio=ComprobanteDomicilio(
            holder_name="María F Núñez García",
            issue_date=date(2026, 7, 3),
        ),
        contrato=Contrato(
            employee_name="María Fernanda Núñez García",
            rfc="NUGA900101AB1",
            curp="NUGA900101MJCZNR09",
            signed_date=date(2026, 9, 28),
            start_date=date(2026, 10, 1),
        ),
    )


def _rule_fixture(
    name: str,
    application: Application,
    extracted: ExtractedFile,
    settings: Settings | None = None,
) -> dict[str, object]:
    settings = settings or Settings()
    rules = run_rules(application, extracted, settings)
    return {
        "name": name,
        "application": application.model_dump(mode="json"),
        "extracted": extracted.model_dump(mode="json"),
        "address_max_age_days": settings.address_max_age_days,
        "contract_max_gap_days": settings.contract_max_gap_days,
        "rules": [rule.model_dump() for rule in rules],
    }


def _rule_fixtures() -> list[dict[str, object]]:
    clean = _rule_fixture("clean", _application(), _extracted())
    name_miss = _extracted()
    assert name_miss.identificacion is not None
    name_miss.identificacion.full_name = "Diego Torres Vega"
    rfc_miss = _extracted()
    assert rfc_miss.constancia_fiscal is not None
    rfc_miss.constancia_fiscal.rfc = "NUGA900101ZZ9"
    curp_miss = _extracted()
    assert curp_miss.constancia_fiscal is not None
    curp_miss.constancia_fiscal.curp = "NUGA900101MJCZNR00"
    optional_curp = _extracted()
    assert optional_curp.contrato is not None
    optional_curp.contrato.curp = None
    bad_contract_curp = _extracted()
    assert bad_contract_curp.contrato is not None
    bad_contract_curp.contrato.curp = "DIFFERENTCURP00000"
    address_old = _extracted()
    assert address_old.comprobante_domicilio is not None
    address_old.comprobante_domicilio.issue_date = date(2026, 7, 2)
    address_future = _extracted()
    assert address_future.comprobante_domicilio is not None
    address_future.comprobante_domicilio.issue_date = date(2026, 10, 6)
    gap_ok = _extracted()
    assert gap_ok.contrato is not None
    gap_ok.contrato.start_date = date(2026, 10, 8)
    gap_ok.contrato.signed_date = date(2026, 10, 5)
    gap_over = _extracted()
    assert gap_over.contrato is not None
    gap_over.contrato.start_date = date(2026, 10, 9)
    gap_over.contrato.signed_date = date(2026, 10, 5)
    missing_signature = _extracted()
    assert missing_signature.contrato is not None
    missing_signature.contrato.signed_date = None
    signed_after = _extracted()
    assert signed_after.contrato is not None
    signed_after.contrato.signed_date = date(2026, 10, 4)
    signed_after.contrato.start_date = date(2026, 10, 1)
    no_contract = _extracted()
    no_contract.contrato = None
    no_proof = _extracted()
    no_proof.comprobante_domicilio = None
    return [
        clean,
        _rule_fixture("name_mismatch", _application(), name_miss),
        _rule_fixture("rfc_mismatch", _application(), rfc_miss),
        _rule_fixture("curp_mismatch", _application(), curp_miss),
        _rule_fixture("contract_curp_optional", _application(), optional_curp),
        _rule_fixture("contract_curp_checked", _application(), bad_contract_curp),
        _rule_fixture("address_91_days", _application(), address_old),
        _rule_fixture("address_future", _application(), address_future),
        _rule_fixture("contract_gap_7", _application(), gap_ok),
        _rule_fixture("contract_gap_8", _application(), gap_over),
        _rule_fixture("missing_signature", _application(), missing_signature),
        _rule_fixture("signed_after_start", _application(), signed_after),
        _rule_fixture("missing_contract", _application(), no_contract),
        _rule_fixture("missing_proof", _application(), no_proof),
    ]


def _report_blob(application: Application, documents: dict[str, str]) -> dict[str, object]:
    request = ValidateTextRequest(
        application=application,
        documents=[
            InlineDocument(doc_type=DocType(doc_type), text=text)
            for doc_type, text in documents.items()
        ],
    )
    report = validate_texts(request, extractor=DeterministicExtractor())
    return {
        "overall_passed": report.overall_passed,
        "rules": [rule.model_dump() for rule in report.rules],
        "warnings": list(report.warnings),
        "extracted": report.extracted.model_dump(mode="json"),
    }


def _text_fixtures() -> list[dict[str, object]]:
    application = _application(
        case_id="TEXTO",
        full_name="Ana Sofía Pérez Silva",
        rfc="PESA800408IG8",
        curp="PESA800408MJCRLN18",
    )
    constancia = (
        "CONSTANCIA DE SITUACION FISCAL\n"
        "Contribuyente: Ana Sofía Pérez Silva\n"
        "R.F.C.: PESA-800408-IG8\n"
        "Clave CURP: PESA800408MJCRLN18\n"
        "C.P. fiscal: 44100\n"
        "Emitida: 2026-09-10\n"
        "Situacion: Activo\n"
    )
    only = {"constancia_fiscal": constancia}
    blank = {"identificacion": "   "}
    return [
        {
            "name": "constancia_without_banner",
            "application": application.model_dump(mode="json"),
            "documents": only,
            "address_max_age_days": 90,
            "contract_max_gap_days": 7,
            "expected": _report_blob(application, only),
        },
        {
            "name": "blank_identificacion",
            "application": application.model_dump(mode="json"),
            "documents": blank,
            "address_max_age_days": 90,
            "contract_max_gap_days": 7,
            "expected": _report_blob(application, blank),
        },
    ]


def _cases() -> list[dict[str, object]]:
    manifest = json.loads((GOLDEN / "manifest.json").read_text(encoding="utf-8"))
    cases: list[dict[str, object]] = []
    for case_id in manifest["cases"]:
        folder = GOLDEN / "cases" / case_id
        application = Application.model_validate(
            json.loads((folder / "application.json").read_text(encoding="utf-8"))
        )
        labels = Labels.model_validate(
            json.loads((folder / "labels.json").read_text(encoding="utf-8"))
        )
        documents = {
            doc_type.value: (folder / filename).read_text(encoding="utf-8")
            for doc_type, filename in DOC_FILES.items()
        }
        expected = _report_blob(application, documents)
        for rule in expected["rules"]:
            assert isinstance(rule, dict)
            labeled = labels.expected_rules[str(rule["rule_id"])]
            if labeled.passed != rule["passed"] or labeled.reason != rule["reason"]:
                raise RuntimeError(f"{case_id} {rule['rule_id']} disagrees with labels.json")
        cases.append(
            {
                "case_id": case_id,
                "defects": list(labels.defects),
                "notes": list(labels.notes),
                "application": application.model_dump(mode="json"),
                "documents": documents,
                "expected": expected,
            }
        )
    return cases


def _eval_public() -> dict[str, object]:
    report = json.loads(EVAL_REPORT.read_text(encoding="utf-8"))
    field_docs = {}
    for name, block in report["fields"]["by_document"].items():
        field_docs[name] = {
            "slots": block["slots"],
            "exact_matches": block["exact_matches"],
            "precision": block["precision"],
            "recall": block["recall"],
        }
    rules = {}
    for name, block in report["rules"].items():
        rules[name] = {
            "support_fail": block["support_fail"],
            "support_pass": block["support_pass"],
            "precision": block["precision"],
            "recall": block["recall"],
            "accuracy": block["accuracy"],
        }
    overall = report["overall"]
    return {
        "dataset": report["dataset"],
        "seed": report["seed"],
        "cases": report["cases"],
        "positive_class": report["positive_class"],
        "parser_backend": report["parser_backend"],
        "extractor_backend": report["extractor_backend"],
        "contract_max_gap_days": report["contract_max_gap_days"],
        "address_max_age_days": report["address_max_age_days"],
        "timing": report["timing"],
        "rules": rules,
        "overall": {
            "support_fail": overall["support_fail"],
            "support_pass": overall["support_pass"],
            "precision": overall["precision"],
            "recall": overall["recall"],
            "accuracy": overall["accuracy"],
        },
        "fields": {
            "slots": report["fields"]["slots"],
            "exact_matches": report["fields"]["exact_matches"],
            "precision": report["fields"]["precision"],
            "recall": report["fields"]["recall"],
            "by_document": field_docs,
        },
        "disagreement_count": len(report["disagreements"]),
    }


def build_payload() -> dict[str, object]:
    manifest = json.loads((GOLDEN / "manifest.json").read_text(encoding="utf-8"))
    return {
        "source": {
            "golden": "data/golden",
            "dataset": manifest["name"],
            "seed": manifest["seed"],
            "case_count": manifest["case_count"],
            "company": manifest["company"],
            "as_of": manifest["as_of"],
            "rules": "src/docval/rules.py",
            "extractor": "src/docval/extractors.py",
            "eval_report": "reports/eval/report.json",
        },
        "policy": {"address_max_age_days": 90, "contract_max_gap_days": 7},
        "eval": _eval_public(),
        "cases": _cases(),
        "rule_fixtures": _rule_fixtures(),
        "text_fixtures": _text_fixtures(),
        "name_pairs": [
            {"left": left, "right": right, "match": names_match(left, right)}
            for left, right in NAME_PAIRS
        ],
        "ratios": [
            {"left": left, "right": right, "ratio": SequenceMatcher(None, left, right).ratio()}
            for left, right in RATIO_PAIRS
        ],
    }


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(payload['cases'])} cases)")


if __name__ == "__main__":
    main()
