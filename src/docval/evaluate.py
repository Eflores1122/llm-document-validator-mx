"""Score pipeline decisions against a golden dataset."""

from __future__ import annotations

import importlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from docval.config import Settings, load_settings
from docval.pipeline import validate_case_dir
from docval.rules import RULE_IDS
from docval.schemas import ExtractedFile, FileReport, Labels
from docval.textutil import collapse_ws, names_match, normalize_id

# (document attribute, field, comparator)
FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("identificacion", "full_name", "name"),
    ("identificacion", "rfc", "rfc"),
    ("identificacion", "curp", "curp"),
    ("identificacion", "birth_date", "date"),
    ("identificacion", "address", "exact"),
    ("identificacion", "sex", "exact"),
    ("constancia_fiscal", "holder_name", "name"),
    ("constancia_fiscal", "rfc", "rfc"),
    ("constancia_fiscal", "curp", "curp"),
    ("constancia_fiscal", "postal_code", "exact"),
    ("constancia_fiscal", "issue_date", "date"),
    ("constancia_fiscal", "tax_status", "exact"),
    ("comprobante_domicilio", "holder_name", "name"),
    ("comprobante_domicilio", "street", "exact"),
    ("comprobante_domicilio", "neighborhood", "exact"),
    ("comprobante_domicilio", "city", "exact"),
    ("comprobante_domicilio", "state", "exact"),
    ("comprobante_domicilio", "postal_code", "exact"),
    ("comprobante_domicilio", "issue_date", "date"),
    ("comprobante_domicilio", "issuer", "exact"),
    ("contrato", "employee_name", "name"),
    ("contrato", "rfc", "rfc"),
    ("contrato", "curp", "curp"),
    ("contrato", "employer", "exact"),
    ("contrato", "role", "exact"),
    ("contrato", "signed_date", "date"),
    ("contrato", "start_date", "date"),
    ("contrato", "contract_kind", "exact"),
)


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    def add_fail_class(self, expected_pass: bool, predicted_pass: bool) -> None:
        """Count a defect (rule failure) as the positive class."""
        expected_fail = not expected_pass
        predicted_fail = not predicted_pass
        if expected_fail and predicted_fail:
            self.tp += 1
        elif predicted_fail:
            self.fp += 1
        elif expected_fail:
            self.fn += 1
        else:
            self.tn += 1

    def precision(self) -> float | None:
        denom = self.tp + self.fp
        if denom == 0:
            return None
        return self.tp / denom

    def recall(self) -> float | None:
        denom = self.tp + self.fn
        if denom == 0:
            return None
        return self.tp / denom

    def accuracy(self) -> float | None:
        denom = self.tp + self.fp + self.tn + self.fn
        if denom == 0:
            return None
        return (self.tp + self.tn) / denom

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "tn": self.tn,
            "fn": self.fn,
            "precision": _round(self.precision()),
            "recall": _round(self.recall()),
            "accuracy": _round(self.accuracy()),
            "support_fail": self.tp + self.fn,
            "support_pass": self.tn + self.fp,
        }


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def values_match(kind: str, gold: object, pred: object) -> bool:
    if _missing(gold) and _missing(pred):
        return True
    if _missing(gold) or _missing(pred):
        return False
    if kind == "name":
        return names_match(str(gold), str(pred))
    if kind in {"rfc", "curp"}:
        return normalize_id(str(gold)) == normalize_id(str(pred))
    if kind == "money":
        return abs(float(gold) - float(pred)) < 0.02  # type: ignore[arg-type]
    if kind == "date":
        return _as_date(gold) == _as_date(pred)
    if kind == "exact":
        return collapse_ws(str(gold)) == collapse_ws(str(pred))
    raise ValueError(f"unknown comparator {kind}")


def _as_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _field(extracted: ExtractedFile | None, document: str, field: str) -> object:
    if extracted is None:
        return None
    model = getattr(extracted, document)
    if model is None:
        return None
    return getattr(model, field)


def field_mismatches(report: FileReport, labels: Labels) -> list[str]:
    """Human-readable slots where extraction disagreed with the printed truth."""
    mismatches: list[str] = []
    for document, field, kind in FIELD_SPECS:
        gold = _field(labels.truth, document, field)
        pred = _field(report.extracted, document, field)
        if not values_match(kind, gold, pred):
            mismatches.append(f"{document}.{field}: expected {gold!r} but extracted {pred!r}")
    return mismatches


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def run_eval(golden: Path, out: Path, settings: Settings | None = None) -> dict[str, Any]:
    """Run every golden case and write report.json plus report.md."""
    settings = settings or load_settings()
    importlib.import_module("pdfplumber")
    importlib.import_module("pypdf")
    manifest = json.loads((golden / "manifest.json").read_text(encoding="utf-8"))
    case_ids = [str(case_id) for case_id in manifest["cases"]]
    rule_counts = {rule_id: Counts() for rule_id in RULE_IDS}
    overall = Counts()
    field_counts = Counts()
    field_slots = 0
    field_matches = 0
    by_document: dict[str, Counts] = {}
    by_document_slots: dict[str, list[int]] = {}
    disagreements: list[dict[str, str]] = []
    case_results: list[dict[str, object]] = []
    timings: list[float] = []
    parser_backend = ""
    extractor_backend = ""

    for case_id in case_ids:
        case_dir = golden / "cases" / case_id
        report = validate_case_dir(case_dir, settings=settings)
        labels = Labels.model_validate(
            json.loads((case_dir / "labels.json").read_text(encoding="utf-8"))
        )
        parser_backend = report.parser_backend
        extractor_backend = report.extractor_backend
        timings.append(report.elapsed_ms)
        failed: list[str] = []
        expected_fail = False
        predicted_fail = False
        for rule_id in RULE_IDS:
            expected = labels.expected_rules[rule_id]
            actual = next(rule for rule in report.rules if rule.rule_id == rule_id)
            rule_counts[rule_id].add_fail_class(expected.passed, actual.passed)
            if not actual.passed:
                failed.append(rule_id)
                predicted_fail = True
            if not expected.passed:
                expected_fail = True
            if actual.passed != expected.passed:
                disagreements.append(
                    {
                        "case_id": case_id,
                        "rule_id": rule_id,
                        "expected_passed": str(expected.passed).lower(),
                        "predicted_passed": str(actual.passed).lower(),
                        "predicted_reason": actual.reason,
                        "expected_reason": expected.reason,
                    }
                )
        overall.add_fail_class(not expected_fail, not predicted_fail)
        for document, field, kind in FIELD_SPECS:
            gold = _field(labels.truth, document, field)
            pred = _field(report.extracted, document, field)
            matched = values_match(kind, gold, pred)
            field_slots += 1
            field_matches += int(matched)
            doc_counts = by_document.setdefault(document, Counts())
            slots = by_document_slots.setdefault(document, [0, 0])
            slots[0] += 1
            slots[1] += int(matched)
            if matched and _missing(gold):
                doc_counts.tn += 1
                field_counts.tn += 1
            elif matched:
                doc_counts.tp += 1
                field_counts.tp += 1
            elif _missing(gold):
                doc_counts.fp += 1
                field_counts.fp += 1
            elif _missing(pred):
                doc_counts.fn += 1
                field_counts.fn += 1
            else:
                doc_counts.fp += 1
                doc_counts.fn += 1
                field_counts.fp += 1
                field_counts.fn += 1
        case_results.append(
            {
                "case_id": case_id,
                "overall_passed": report.overall_passed,
                "elapsed_ms": report.elapsed_ms,
                "failed_rules": failed,
                "defects": labels.defects,
            }
        )

    fields = field_counts.as_dict()
    fields["slots"] = field_slots
    fields["exact_matches"] = field_matches
    fields["accuracy"] = _round(field_matches / field_slots) if field_slots else None
    fields["by_document"] = {
        name: {
            **counts.as_dict(),
            "slots": by_document_slots[name][0],
            "exact_matches": by_document_slots[name][1],
            "accuracy": _round(by_document_slots[name][1] / by_document_slots[name][0]),
        }
        for name, counts in by_document.items()
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "dataset": manifest.get("name"),
        "seed": manifest.get("seed"),
        "cases": len(case_ids),
        "positive_class": "fail",
        "parser_backend": parser_backend,
        "extractor_backend": extractor_backend,
        "contract_max_gap_days": settings.contract_max_gap_days,
        "address_max_age_days": settings.address_max_age_days,
        "timing": {
            "mean_ms": round(sum(timings) / len(timings), 3),
            "p50_ms": round(_percentile(timings, 50), 3),
            "p95_ms": round(_percentile(timings, 95), 3),
            "max_ms": round(max(timings), 3),
            "total_ms": round(sum(timings), 3),
        },
        "rules": {rule_id: rule_counts[rule_id].as_dict() for rule_id in RULE_IDS},
        "overall": overall.as_dict(),
        "fields": fields,
        "disagreements": disagreements,
        "case_results": case_results,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    """Render the eval report, including the tables the README quotes."""
    timing = payload["timing"]
    lines = [
        "# Docval evaluation",
        "",
        f"Dataset `{payload['dataset']}` seed {payload['seed']}, {payload['cases']} files.",
        f"Parser `{payload['parser_backend']}`, extractor `{payload['extractor_backend']}`.",
        "The positive class for precision and recall is a **fail** "
        "(a defect the reviewer should catch).",
        f"Contract start window {payload['contract_max_gap_days']} days. "
        f"Address window {payload['address_max_age_days']} days.",
        "",
        "<!-- eval-table:start -->",
        "| Rule | Fail | Pass | Precision | Recall | Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rule_id, stats in payload["rules"].items():
        lines.append(_rule_row(rule_id, stats))
    lines.append(_rule_row("overall", payload["overall"]))
    lines.append("<!-- eval-table:end -->")
    lines.extend(
        [
            "",
            "<!-- field-table:start -->",
            "| Document | Slots | Exact match | Precision | Recall |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, stats in payload["fields"]["by_document"].items():
        lines.append(
            f"| {name} | {stats['slots']} | {_pct(stats['accuracy'])} | "
            f"{_pct(stats['precision'])} | {_pct(stats['recall'])} |"
        )
    fields = payload["fields"]
    lines.append(
        f"| all fields | {fields['slots']} | {_pct(fields['accuracy'])} | "
        f"{_pct(fields['precision'])} | {_pct(fields['recall'])} |"
    )
    lines.append("<!-- field-table:end -->")
    lines.extend(
        [
            "",
            "<!-- eval-timing:start -->",
            (
                f"Mean {timing['mean_ms']:.1f} ms per file "
                f"(p50 {timing['p50_ms']:.1f} ms, p95 {timing['p95_ms']:.1f} ms) "
                f"over {payload['cases']} files."
            ),
            "<!-- eval-timing:end -->",
            "",
        ]
    )
    if payload["disagreements"]:
        lines.append("## Disagreements")
        lines.append("")
        for item in payload["disagreements"]:
            lines.append(
                f"- `{item['case_id']}` `{item['rule_id']}`: "
                f"expected pass={item['expected_passed']}, "
                f"predicted pass={item['predicted_passed']}. {item['predicted_reason']}"
            )
    else:
        lines.append("No disagreements between the pipeline and the golden labels.")
    lines.append("")
    return "\n".join(lines)


def _rule_row(name: str, stats: dict[str, Any]) -> str:
    return (
        f"| {name} | {stats['support_fail']} | {stats['support_pass']} | "
        f"{_pct(stats['precision'])} | {_pct(stats['recall'])} | {_pct(stats['accuracy'])} |"
    )


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def markdown_section(text: str, start: str, end: str) -> str:
    start_at = text.index(start) + len(start)
    end_at = text.index(end, start_at)
    return text[start_at:end_at].strip()
