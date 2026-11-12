"""The static site data stays tied to the Python rules and the eval report."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _export():
    path = ROOT / "scripts" / "export_site_data.py"
    spec = importlib.util.spec_from_file_location("export_site_data", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_committed_site_data_matches_python() -> None:
    module = _export()
    committed = json.loads((ROOT / "site" / "data" / "site.json").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(module.build_payload(), ensure_ascii=False))
    assert committed == fresh


def test_readme_links_the_site_at_the_top() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    head = readme.split("## Problem", 1)[0]
    assert "https://eflores1122.github.io/llm-document-validator-mx/" in head


def test_site_says_the_scores_are_not_a_vendor_measurement() -> None:
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert 'data-i18n="measureNote"' in html
    assert "Not a LlamaParse or OpenAI score." in app
    assert "No es una medición de LlamaParse ni de OpenAI." in app


def test_pages_workflow_publishes_the_site() -> None:
    text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    for snippet in (
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
        "pages: write",
        "id-token: write",
        "workflow_dispatch",
        "branches: [main]",
    ):
        assert snippet in text


def test_browser_engine_matches_python() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    subprocess.run([node, "site/check-engine.mjs"], check=True, cwd=ROOT)
