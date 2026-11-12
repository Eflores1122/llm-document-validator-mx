"""The published score stays on the no-key path and says what 100% means."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from docval.cli import app
from docval.errors import ExtractionError
from docval.evaluate import Counts, field_mismatches, record_field, render_markdown, run_eval
from docval.extractors import OpenAIExtractor
from docval.generate import write_dataset

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_field_score_counts_blanks_and_disagreements() -> None:
    both_empty = Counts()
    assert record_field(both_empty, "exact", None, None) is True
    assert (both_empty.tn, both_empty.tp, both_empty.fp, both_empty.fn) == (1, 0, 0, 0)

    match = Counts()
    assert record_field(match, "exact", "Activo", "Activo") is True
    assert match.tp == 1

    wrong = Counts()
    assert record_field(wrong, "exact", "Activo", "Cancelado") is False
    assert (wrong.fp, wrong.fn) == (1, 1)
    assert wrong.precision() == 0
    assert wrong.recall() == 0

    missed = Counts()
    assert record_field(missed, "date", "2026-10-01", None) is False
    assert (missed.fn, missed.fp) == (1, 0)

    invented = Counts()
    assert record_field(invented, "exact", None, "Talento") is False
    assert (invented.fp, invented.fn) == (1, 0)


def test_file_level_fails_are_not_the_sum_of_rule_rows() -> None:
    multi = 0
    single = 0
    clean = 0
    rule_events = 0
    cases = ROOT / "data" / "golden" / "cases"
    for labels_path in sorted(cases.glob("*/labels.json")):
        payload = json.loads(labels_path.read_text(encoding="utf-8"))
        failed = [
            rule_id for rule_id, row in payload["expected_rules"].items() if not row["passed"]
        ]
        rule_events += len(failed)
        if len(failed) > 1:
            multi += 1
        elif len(failed) == 1:
            single += 1
        else:
            clean += 1
    assert clean == 6
    assert single == 14
    assert multi == 4
    assert single + multi == 18
    assert rule_events == 22


def test_only_blank_printed_slots_are_missing_signatures() -> None:
    blanks: list[tuple[str, str]] = []
    cases = ROOT / "data" / "golden" / "cases"
    for labels_path in sorted(cases.glob("*/labels.json")):
        payload = json.loads(labels_path.read_text(encoding="utf-8"))
        signed = payload["truth"]["contrato"]["signed_date"]
        if signed is None:
            blanks.append((labels_path.parent.name, "contrato.signed_date"))
        assert payload["truth"]["contrato"]["start_date"]
    assert blanks == [
        ("EXP-0009", "contrato.signed_date"),
        ("EXP-0021", "contrato.signed_date"),
    ]


def test_eval_ignores_ambient_vendor_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "llx-test-not-real")

    def refuse_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("no-key eval attempted a network call")

    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
    golden = tmp_path / "golden"
    write_dataset(golden, cases=2, seed=42)
    payload = run_eval(golden, tmp_path / "eval")
    assert payload["parser_backend"].startswith("local:")
    assert payload["extractor_backend"] == "deterministic"
    assert payload["disagreements"] == []


def test_eval_flag_can_still_select_openai(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    seen: list[str] = []

    def stop(self: OpenAIExtractor, _parsed: object) -> object:
        seen.append(self.backend_name)
        raise ExtractionError("stopped before any API call")

    monkeypatch.setattr(OpenAIExtractor, "extract", stop)
    golden = tmp_path / "golden"
    write_dataset(golden, cases=1, seed=3)
    payload = run_eval(golden, tmp_path / "eval", extractor_name="openai")
    assert seen == ["openai", "openai", "openai", "openai"]
    assert payload["extractor_backend"] == "openai"
    assert payload["parser_backend"].startswith("local:")
    assert payload["disagreements"]
    note = render_markdown(payload)
    assert "LlamaParse and OpenAI are not scored." not in note
    assert "extractor `openai`" in note
    assert "not the committed no-key score" in note


def test_cli_eval_stays_local_when_vendor_keys_are_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("LLAMA_CLOUD_API_KEY", "llx-test-not-real")

    def refuse_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("no-key eval attempted a network call")

    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
    golden = tmp_path / "golden"
    write_dataset(golden, cases=1, seed=4)
    out = tmp_path / "eval"
    result = runner.invoke(app, ["eval", "--golden", str(golden), "--out", str(out)])
    assert result.exit_code == 0, result.output
    payload = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert payload["parser_backend"].startswith("local:")
    assert payload["extractor_backend"] == "deterministic"
    assert "LlamaParse and OpenAI are not scored." in (out / "report.md").read_text(
        encoding="utf-8"
    )


def test_cli_eval_openai_without_a_key_fails(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    write_dataset(golden, cases=1, seed=5)
    result = runner.invoke(
        app,
        [
            "eval",
            "--golden",
            str(golden),
            "--out",
            str(tmp_path / "eval"),
            "--extractor",
            "openai",
        ],
    )
    assert result.exit_code != 0
    assert "OPENAI_API_KEY" in result.output


def test_committed_eval_markdown_matches_renderer() -> None:
    payload = json.loads((ROOT / "reports" / "eval" / "report.json").read_text(encoding="utf-8"))
    rendered = render_markdown(payload)
    assert rendered == (ROOT / "reports" / "eval" / "report.md").read_text(encoding="utf-8")
    assert "LlamaParse and OpenAI are not scored." in rendered
    assert "does not imply that every printed field was recovered" in rendered
    assert "Field recovery is the field table." in rendered
    assert "18 files fail and 6 pass" in rendered
    assert "22 failing rule" in rendered
    assert "2 of those matches are slots" in rendered


def test_reading_note_follows_the_backends_that_ran() -> None:
    def report(parser: str, extractor: str) -> str:
        stats = {
            "support_fail": 0,
            "support_pass": 1,
            "precision": 1.0,
            "recall": 1.0,
            "accuracy": 1.0,
        }
        payload = {
            "dataset": "demo",
            "seed": 1,
            "cases": 1,
            "parser_backend": parser,
            "extractor_backend": extractor,
            "contract_max_gap_days": 7,
            "address_max_age_days": 90,
            "timing": {"mean_ms": 1.0, "p50_ms": 1.0, "p95_ms": 1.0},
            "rules": {"name_consistency": stats},
            "overall": stats,
            "fields": {
                "slots": 1,
                "exact_matches": 1,
                "accuracy": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "tn": 0,
                "by_document": {
                    "identificacion": {
                        "slots": 1,
                        "accuracy": 1.0,
                        "precision": 1.0,
                        "recall": 1.0,
                    }
                },
            },
            "disagreements": [],
        }
        return render_markdown(payload)

    local = report("local:pdfplumber", "deterministic")
    assert "LlamaParse and OpenAI are not scored." in local
    for parser, extractor in (
        ("local:pdfplumber", "openai"),
        ("llamaparse", "deterministic"),
        ("llamaparse", "openai"),
    ):
        text = report(parser, extractor)
        assert "LlamaParse and OpenAI are not scored." not in text
        assert f"parser `{parser}`" in text
        assert f"extractor `{extractor}`" in text
        assert "not the committed no-key score" in text


def test_rule_agreement_can_hide_fields_the_rules_do_not_read() -> None:
    from docval.config import Settings
    from docval.pipeline import validate_case_dir
    from docval.rules import run_rules
    from docval.schemas import Labels

    case_dir = ROOT / "data" / "golden" / "cases" / "EXP-0001"
    report = validate_case_dir(case_dir)
    labels = Labels.model_validate(
        json.loads((case_dir / "labels.json").read_text(encoding="utf-8"))
    )
    assert report.extracted.constancia_fiscal is not None
    assert report.extracted.contrato is not None
    report.extracted.constancia_fiscal.tax_status = "Cancelado"
    report.extracted.contrato.employer = "Otra Empresa SA de CV"
    rerun = run_rules(report.application, report.extracted, Settings())
    for rule in rerun:
        assert rule.passed == labels.expected_rules[rule.rule_id].passed
    mismatches = field_mismatches(report, labels)
    assert any("tax_status" in item for item in mismatches)
    assert any("employer" in item for item in mismatches)


def test_ci_runs_the_nokey_cli() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "unset OPENAI_API_KEY" in text
    assert "unset LLAMA_CLOUD_API_KEY" in text or "unset OPENAI_API_KEY LLAMA_CLOUD_API_KEY" in text
    assert "python -m docval eval" in text
    assert 'report["extractor_backend"] == "deterministic"' in text
    assert "https_proxy" in text
