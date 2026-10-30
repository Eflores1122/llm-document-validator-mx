"""End-to-end checks on generated files, the CLI, and the HTTP API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from docval.cli import app
from docval.evaluate import field_mismatches, run_eval
from docval.generate import build_cases, plan_for_index, write_dataset
from docval.pipeline import validate_case_dir, validate_texts
from docval.rules import RULE_IDS
from docval.schemas import Labels, ValidateTextRequest

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_plan_covers_boundaries_and_both_classes() -> None:
    assert plan_for_index(1).address_age_days == 90
    assert plan_for_index(2).contract_mode == "boundary"
    assert "name_mismatch" in plan_for_index(3).defects
    assert plan_for_index(6).address_age_days >= 91
    assert plan_for_index(7).contract_mode == "late_start"
    assert plan_for_index(8).contract_mode == "missing_signature"
    assert plan_for_index(9).address_age_days < 0
    assert plan_for_index(0).name_styles["identificacion"] == "inverted"
    assert plan_for_index(1).name_styles["contrato"] == "accentless"


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_dataset(first, cases=2, seed=42)
    write_dataset(second, cases=2, seed=42)
    for left in first.rglob("*"):
        if left.is_file():
            right = second / left.relative_to(first)
            assert left.read_bytes() == right.read_bytes()


def test_generated_pages_are_marked_fictitious() -> None:
    for case in build_cases(24, seed=42):
        for text in case.texts.values():
            assert "DOCUMENTO FICTICIO" in text
            assert "SIN VALIDEZ OFICIAL" in text


def test_pipeline_matches_labels_and_defines_every_rule(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    write_dataset(golden, cases=24, seed=42)
    support = {rule_id: {"fail": 0, "pass": 0} for rule_id in RULE_IDS}
    for case in build_cases(24, seed=42):
        case_dir = golden / "cases" / case.application.case_id
        report = validate_case_dir(case_dir)
        labels = Labels.model_validate(
            json.loads((case_dir / "labels.json").read_text(encoding="utf-8"))
        )
        mismatches = field_mismatches(report, labels)
        assert mismatches == [], (case.application.case_id, mismatches)
        assert report.parser_backend.startswith("local:")
        assert report.extractor_backend == "deterministic"
        assert "SIN VALIDEZ OFICIAL" not in "".join(report.warnings)
        for rule_id in RULE_IDS:
            expected = labels.expected_rules[rule_id]
            actual = next(rule for rule in report.rules if rule.rule_id == rule_id)
            assert actual.passed == expected.passed, (
                case.application.case_id,
                rule_id,
                actual.reason,
                expected.reason,
                labels.defects,
            )
            support[rule_id]["pass" if expected.passed else "fail"] += 1
        assert report.overall_passed == all(rule.passed for rule in report.rules)
    for rule_id, counts in support.items():
        assert counts["fail"] > 0, rule_id
        assert counts["pass"] > 0, rule_id


def test_inline_validation_catches_a_name_mismatch() -> None:
    clean, _, _, mismatched = build_cases(4, seed=3)
    clean_report = validate_texts(
        ValidateTextRequest(
            application=clean.application,
            documents=[
                {"doc_type": doc_type, "text": text} for doc_type, text in clean.texts.items()
            ],
        )
    )
    assert clean_report.overall_passed
    bad_report = validate_texts(
        ValidateTextRequest(
            application=mismatched.application,
            documents=[
                {"doc_type": doc_type, "text": text} for doc_type, text in mismatched.texts.items()
            ],
        )
    )
    assert not bad_report.overall_passed
    failed = {rule.rule_id for rule in bad_report.rules if not rule.passed}
    assert "name_mismatch" in mismatched.labels.defects
    assert "name_consistency" in failed


def test_cli_generate_run_and_eval(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    generated = runner.invoke(
        app,
        ["generate", "--out", str(golden), "--cases", "12", "--seed", "7"],
    )
    assert generated.exit_code == 0, generated.output
    reports = tmp_path / "reports"
    reviewed = runner.invoke(app, ["run", str(golden), "--out", str(reports), "--parser", "local"])
    assert reviewed.exit_code == 0, reviewed.output
    assert "FAIL" in reviewed.output
    assert "PASS" in reviewed.output
    evaluation = tmp_path / "eval"
    scored = runner.invoke(app, ["eval", "--golden", str(golden), "--out", str(evaluation)])
    assert scored.exit_code == 0, scored.output
    payload = json.loads((evaluation / "report.json").read_text(encoding="utf-8"))
    assert payload["overall"]["accuracy"] == 1
    assert payload["fields"]["accuracy"] == 1
    assert payload["cases"] == 12
    assert (evaluation / "report.md").is_file()


def test_eval_refuses_to_delete_unrelated_directory(tmp_path: Path) -> None:
    target = tmp_path / "notes"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    result = runner.invoke(app, ["generate", "--out", str(target), "--cases", "1", "--force"])
    assert result.exit_code != 0
    assert (target / "keep.txt").is_file()


def test_api_health_validate_and_case_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from docval.api import app as api_app

    golden = tmp_path / "golden"
    write_dataset(golden, cases=4, seed=11)
    monkeypatch.setenv("DOCVAL_GOLDEN_ROOT", str(golden))
    client = TestClient(api_app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["parser_backend"] == "local"
    assert health.json()["extractor_backend"] == "deterministic"
    assert len(client.get("/rules").json()) == len(RULE_IDS)

    case = build_cases(4, seed=11)[3]
    response = client.post(
        "/validate",
        json={
            "application": case.application.model_dump(mode="json"),
            "documents": [
                {"doc_type": doc_type.value, "text": text} for doc_type, text in case.texts.items()
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_passed"] is False
    assert body["extractor_backend"] == "deterministic"

    saved = client.post("/cases/EXP-0001/validate")
    assert saved.status_code == 200, saved.text
    assert saved.json()["case_id"] == "EXP-0001"
    assert client.post("/cases/not-a-case/validate").status_code == 400
    assert client.post("/cases/EXP-9999/validate").status_code == 404


def test_missing_banner_is_a_warning_not_a_rule() -> None:
    case = build_cases(1, seed=1)[0]
    documents = [
        {"doc_type": doc_type, "text": f"Tipo: {doc_type.value}\nNombre completo: Ana\n"}
        for doc_type in case.texts
    ]
    report = validate_texts(ValidateTextRequest(application=case.application, documents=documents))
    assert any("synthetic-fixture banner" in warning for warning in report.warnings)
    assert report.overall_passed is False


def test_committed_eval_metrics_match_a_fresh_run(tmp_path: Path) -> None:
    committed_path = ROOT / "reports" / "eval" / "report.json"
    if not committed_path.is_file():
        pytest.skip("golden eval report is not generated yet")
    fresh = run_eval(ROOT / "data" / "golden", tmp_path / "eval")
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    assert fresh["rules"] == committed["rules"]
    assert fresh["overall"] == committed["overall"]
    assert fresh["fields"] == committed["fields"]
    assert fresh["disagreements"] == committed["disagreements"]
    assert fresh["timing"]["mean_ms"] < 5000


def test_readme_quotes_the_committed_eval_report() -> None:
    report_md = ROOT / "reports" / "eval" / "report.md"
    readme = ROOT / "README.md"
    if not report_md.is_file():
        pytest.skip("eval report is not generated yet")
    report = report_md.read_text(encoding="utf-8")
    readme_text = readme.read_text(encoding="utf-8")
    for start, end in (
        ("<!-- eval-table:start -->", "<!-- eval-table:end -->"),
        ("<!-- field-table:start -->", "<!-- field-table:end -->"),
        ("<!-- eval-timing:start -->", "<!-- eval-timing:end -->"),
    ):
        section = report.split(start, 1)[1].split(end, 1)[0].strip()
        assert section in readme_text
