"""Command line for generating, validating, and scoring synthetic onboarding files."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from docval import __version__
from docval.config import load_settings
from docval.errors import DocvalError
from docval.evaluate import render_markdown, run_eval
from docval.generate import write_dataset
from docval.pipeline import iter_case_dirs, validate_case_dir

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Print the version and exit."
        ),
    ] = False,
) -> None:
    """Validate synthetic Mexican employee-onboarding files."""


@app.command()
def generate(
    out: Annotated[Path, typer.Option("--out", help="Dataset directory to create.")] = Path(
        "data/golden"
    ),
    cases: Annotated[int, typer.Option("--cases", min=1, max=240)] = 24,
    seed: Annotated[int, typer.Option("--seed")] = 42,
    force: Annotated[bool, typer.Option("--force", help="Replace an existing dataset.")] = False,
) -> None:
    """Write a seeded golden dataset of watermarked synthetic PDFs."""
    try:
        manifest = write_dataset(out, cases=cases, seed=seed, force=force)
    except DocvalError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Wrote {manifest['case_count']} cases to {out} (seed {manifest['seed']}).")


@app.command()
def run(
    path: Annotated[Path, typer.Argument(help="Case directory or dataset root.")],
    out: Annotated[Path, typer.Option("--out", help="Directory for JSON reports.")] = Path(
        "reports/cases"
    ),
    parser: Annotated[
        str | None,
        typer.Option("--parser", help="local, llamaparse, or omit to auto-select."),
    ] = None,
    extractor: Annotated[
        str | None,
        typer.Option("--extractor", help="deterministic, mock, openai, or omit to auto-select."),
    ] = None,
) -> None:
    """Parse, extract, and review one file or every file in a dataset."""
    settings = load_settings()
    try:
        case_dirs = iter_case_dirs(path)
    except DocvalError as exc:
        raise typer.BadParameter(str(exc)) from exc
    out.mkdir(parents=True, exist_ok=True)
    review_failures = 0
    errors = 0
    for case_dir in case_dirs:
        try:
            report = validate_case_dir(
                case_dir,
                settings=settings,
                parser_name=parser,
                extractor_name=extractor,
            )
        except DocvalError as exc:
            typer.echo(f"{case_dir.name}  ERROR  {exc}")
            errors += 1
            continue
        destination = out / f"{report.case_id}.json"
        destination.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        status = "PASS" if report.overall_passed else "FAIL"
        if not report.overall_passed:
            review_failures += 1
        failed_rules = ", ".join(rule.rule_id for rule in report.rules if not rule.passed)
        suffix = f"  {failed_rules}" if failed_rules else ""
        typer.echo(f"{report.case_id}  {status}  {report.elapsed_ms:.1f} ms{suffix}")
    passed = len(case_dirs) - review_failures - errors
    typer.echo(
        f"{passed} passed, {review_failures} failed review, {errors} errors. Reports in {out}."
    )
    if errors:
        raise typer.Exit(code=1)


@app.command("eval")
def eval_cmd(
    golden: Annotated[Path, typer.Option("--golden", help="Golden dataset root.")] = Path(
        "data/golden"
    ),
    out: Annotated[
        Path, typer.Option("--out", help="Directory for the Markdown and JSON report.")
    ] = Path("reports/eval"),
    parser: Annotated[
        str,
        typer.Option(
            "--parser",
            help="Parser to score. Default local, even when LLAMA_CLOUD_API_KEY is set.",
        ),
    ] = "local",
    extractor: Annotated[
        str,
        typer.Option(
            "--extractor",
            help="Extractor to score. Default deterministic, even when OPENAI_API_KEY is set.",
        ),
    ] = "deterministic",
) -> None:
    """Score golden labels. Defaults to the no-key parser and extractor."""
    if not (golden / "manifest.json").is_file():
        raise typer.BadParameter(f"{golden} has no manifest.json. Run `docval generate` first.")
    try:
        payload = run_eval(
            golden,
            out,
            load_settings(),
            parser_name=parser,
            extractor_name=extractor,
        )
    except DocvalError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(render_markdown(payload))
    typer.echo(f"Wrote {out / 'report.md'} and {out / 'report.json'}.")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8000,
) -> None:
    """Serve the small HTTP API. Requires the api extra (fastapi, uvicorn)."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter("Install the api extra: pip install 'docval[api]'") from exc
    uvicorn.run("docval.api:app", host=host, port=port)
