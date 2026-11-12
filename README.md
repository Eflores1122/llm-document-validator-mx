# Docval

Sitio: <https://eflores1122.github.io/llm-document-validator-mx/>

[![CI](https://github.com/Eflores1122/llm-document-validator-mx/actions/workflows/ci.yml/badge.svg)](https://github.com/Eflores1122/llm-document-validator-mx/actions/workflows/ci.yml)

Reference project for an LLM-assisted review of Mexican employee-onboarding files. It builds a fully synthetic expediente for a fictitious staffing company, Talento Bajío (printed on each page as Talento Bajio SA de CV): an identification summary, a constancia de situación fiscal, a comprobante de domicilio, and a contrato laboral or carta oferta. It parses those pages, extracts structured fields, and checks the questions a reviewer asks of a new hire: do the name, RFC, and CURP agree, is the address proof recent, and do the contract dates line up with the agreed start.

This repository is a reference implementation on synthetic data. Every person, client, and identifier below is fictional. RFC and CURP values only follow the public shape of those identifiers; they are not issued by SAT or RENAPO, and the identification summary is not an official credential (no photograph, barcode, or MRZ).

The default path needs no API keys. LlamaParse and OpenAI are optional backends.

The public site runs those same deterministic rules in the browser. It reviews the committed synthetic onboarding files only: an identification summary, a constancia de situación fiscal, a comprobante de domicilio, and a contrato laboral or carta oferta. It does not score credit, bank, or payment documents. This dataset does not contain them, and it does not contain CFDI.

## Problem

An onboarding file is four documents that must tell one story.

| Document | What the reviewer reads |
| --- | --- |
| Identification summary | Name, CURP, RFC, date of birth. A stand-in for an INE-style id, not an official card. |
| Constancia de situación fiscal | Name, RFC, CURP, fiscal postal code, issue date |
| Comprobante de domicilio | Holder, address, issue date |
| Contrato laboral or carta oferta | Name, RFC, CURP, start date, signature date |

The repetitive failures are cross-document, not inside a single page: a name that belongs to someone else, an RFC or CURP that drifted by a character, a utility bill older than the policy window, a contract start outside the allowed gap, or a contract filed without a signature date. Docval turns that checklist into a per-file report with a pass or fail and a reason for each rule.

## Architecture

```mermaid
flowchart LR
  subgraph caseFolder [Case folder]
    App[application.json]
    PDF[Four watermarked PDFs]
  end
  PDF --> Parser{Parser}
  Parser -->|LLAMA_CLOUD_API_KEY set| Llama[LlamaParse]
  Parser -->|no key| Local[pdfplumber or pypdf]
  Llama --> Text[Document text]
  Local --> Text
  Text --> Extractor{Extractor}
  Extractor -->|OPENAI_API_KEY set| OpenAI[OpenAI structured output]
  Extractor -->|no key| Det[Deterministic extractor]
  OpenAI --> Fields[Pydantic fields]
  Det --> Fields
  App --> Rules[Name, RFC, CURP, address age, contract dates]
  Fields --> Rules
  Rules --> Report[Per-file JSON report]
  Report --> Eval[Precision, recall, accuracy vs labels.json]
```

`application.json` is the hire record (name, RFC, CURP, address, hire date, agreed start). `labels.json` is eval-only. `docval run` never reads it. Labels are produced by running the review rules on the fields that were printed. Those functions read only the fields a rule needs. Recovering every printed field implies the same rule decision. A matching rule score does not, by itself, show that every printed field was recovered. That is what the field table measures. Rule boundaries (the 7-day contract-start tie, the 90-day address tie, accents, initials, surname-first order) are also covered by unit tests that do not go through the generator.

## Quickstart

Requires Python 3.11+. No API keys.

```bash
python -m pip install -e ".[dev,api]"
python -m docval eval
```

That command scores the committed dataset in `data/golden` (24 cases, seed 42) and writes `reports/eval/report.md` and `reports/eval/report.json`. It always uses the local parser and the deterministic extractor, even when `OPENAI_API_KEY` or `LLAMA_CLOUD_API_KEY` is set. Pass `--parser` and `--extractor` to score another backend. That opt-in path is not part of the numbers below.

Review one file:

```bash
python -m docval run data/golden/cases/EXP-0004
```

Regenerate the dataset, run the suite, or start the API:

```bash
python -m docval generate --out data/golden --cases 24 --seed 42 --force
make test
python -m uvicorn docval.api:app --host 127.0.0.1 --port 8000
```

`make test` is what CI runs: Ruff, then pytest, with vendor keys unset. Optional backends:

```bash
pip install -e ".[llm,api]"
# copy .env.example to .env and export OPENAI_API_KEY and/or LLAMA_CLOUD_API_KEY
python -m docval run data/golden/cases/EXP-0001 --parser llamaparse --extractor openai
```

With the keys unset, `--parser llamaparse` and `--extractor openai` exit with a clear error instead of silently calling a vendor. `mock` is an alias for the deterministic extractor.

### HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Selected parser and extractor |
| `GET` | `/rules` | The five review rules |
| `POST` | `/validate` | Hire-record JSON plus document text |
| `POST` | `/cases/{case_id}/validate` | Replay one case under `DOCVAL_GOLDEN_ROOT` |

Case ids must look like `EXP-0001`. The handler resolves the folder and refuses paths outside the dataset root.

## Sample output

Fresh-process runs against the committed fixtures. The milliseconds are `elapsed_ms` from the JSON files in `reports/examples` on the machine that wrote them. Pass, fail, and the rule id are the result to check. The times are not a benchmark.

```text
$ python -m docval run data/golden/cases/EXP-0001 --out reports/examples
EXP-0001  PASS  1.6 ms
1 passed, 0 failed review, 0 errors. Reports in reports/examples.

$ python -m docval run data/golden/cases/EXP-0004 --out reports/examples
EXP-0004  FAIL  2.4 ms  name_consistency
0 passed, 1 failed review, 0 errors. Reports in reports/examples.

$ python -m docval run data/golden/cases/EXP-0008 --out reports/examples
EXP-0008  FAIL  2.4 ms  contract_dates
0 passed, 1 failed review, 0 errors. Reports in reports/examples.
```

`EXP-0004` is a name defect. The hire record, constancia, contract, and proof of address all say Diego Vargas Ortiz. The identification summary says Mariana Hernández Cruz. The full report is `reports/examples/EXP-0004.json`. The rule section is:

```json
[
  {
    "rule_id": "name_consistency",
    "passed": false,
    "reason": "Name mismatch against hire record 'Diego Vargas Ortiz': identificacion 'Mariana Hernández Cruz'."
  },
  {
    "rule_id": "rfc_consistency",
    "passed": true,
    "reason": "RFC agrees on VAOD740128HJK."
  },
  {
    "rule_id": "curp_consistency",
    "passed": true,
    "reason": "CURP agrees on VAOD740128HQTRRG64."
  },
  {
    "rule_id": "address_recency",
    "passed": true,
    "reason": "Proof of address issued 2026-08-12 is 50 days before the hire date (limit 90)."
  },
  {
    "rule_id": "contract_dates",
    "passed": true,
    "reason": "contract start 2026-10-01 vs agreed start 2026-10-01 (0 days <= limit 7); contract signed 2026-09-28 is on or before the start date 2026-10-01."
  }
]
```

`EXP-0008` fails only on the contract start. From `reports/examples/EXP-0008.json`:

> contract start 2026-10-31 vs agreed start 2026-10-01 (30 days > limit 7).

Files that should pass still exercise the matcher. `EXP-0001` prints the identification summary as `PÉREZ SILVA, ANA SOFÍA` while the hire record says `Ana Sofía Pérez Silva`. `EXP-0002` drops accents on the contract (`Ana Sofia Diaz Vazquez` vs `Ana Sofía Díaz Vázquez`) and the proof of address is exactly 90 days old (issued 2026-07-03). `EXP-0003` starts the contract on 2026-10-08, exactly 7 days after the agreed start, on the boundary of the window. All three pass. `EXP-0009` is a different failure: the contract is present but the signature date was never printed, so `contract_dates` fails closed.

## Evaluation

The tables below are the no-key path on the committed synthetic files: parser `local:pdfplumber`, extractor `deterministic`. They are not a LlamaParse or OpenAI result, and they are not an estimate of accuracy on real scans or on layouts this generator does not print.

The positive class for a rule is a **fail**: a defect the reviewer should catch. Precision is the share of predicted failures that are real. Recall is the share of labeled failures the pipeline caught. Accuracy counts both correct passes and correct failures.

`labels.json` stores `expected_rules` by running those same rules on the fields the generator printed. The functions read only the fields a rule needs, so recovering every printed field makes the rules replay the same pass or fail. A perfect rule score does not imply that recovery. A wrong employer name or tax status, which no rule reads, leaves every decision unchanged. Field recovery is the field table. The boundaries (the 7-day contract-start tie, the 90-day address tie, accents, initials, surname-first order) are covered by unit tests that do not go through the generator.

The overall row is one decision per file. A file fails if any rule fails, so its fail count is not the sum of the rule rows. On this dataset, 18 of 24 files fail at least one rule and 6 pass every rule. The rule rows add up to 22 failing decisions because four files fail two rules each.

These tables, and the note under them, are copied from [`reports/eval/report.md`](reports/eval/report.md), produced by `python -m docval eval` on `data/golden` (seed 42, 24 files). That command forces the local parser and the deterministic extractor even when vendor keys are set. There were no disagreements with the labels.

<!-- eval-table:start -->
| Rule | Fail | Pass | Precision | Recall | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| name_consistency | 4 | 20 | 100.0% | 100.0% | 100.0% |
| rfc_consistency | 4 | 20 | 100.0% | 100.0% | 100.0% |
| curp_consistency | 2 | 22 | 100.0% | 100.0% | 100.0% |
| address_recency | 6 | 18 | 100.0% | 100.0% | 100.0% |
| contract_dates | 6 | 18 | 100.0% | 100.0% | 100.0% |
| overall | 18 | 6 | 100.0% | 100.0% | 100.0% |
<!-- eval-table:end -->

Field scores compare extracted values with the printed ground truth (672 slots). Names match under the same policy as the name rule. RFC and CURP are compared after punctuation is removed. Dates and the remaining strings are compared exactly. An empty label and an empty extraction count as a match. On this dataset those two empty matches are `contrato.signed_date` on EXP-0009 and EXP-0021, the files whose contract omits the signature date. Field precision and recall treat a non-empty printed value as the positive class, so those two blanks do not enter that denominator. A wrong non-empty value counts as both a false positive and a false negative, so the two rates move together when extraction is wrong. On this set every slot matched, so both rates are 100%.

<!-- field-table:start -->
| Document | Slots | Exact match | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| identificacion | 144 | 100.0% | 100.0% | 100.0% |
| constancia_fiscal | 144 | 100.0% | 100.0% | 100.0% |
| comprobante_domicilio | 192 | 100.0% | 100.0% | 100.0% |
| contrato | 192 | 100.0% | 100.0% | 100.0% |
| all fields | 672 | 100.0% | 100.0% | 100.0% |
<!-- field-table:end -->

<!-- eval-reading:start -->
These scores use parser `local:pdfplumber` and extractor `deterministic` only. LlamaParse and OpenAI are not scored. Each labels.json expected_rules entry was produced by the same review functions on the fields the generator printed. Those functions read only the fields a rule needs. Recovering every printed field implies the same rule decision. A perfect rule score does not imply that every printed field was recovered, because a wrong value the rules do not read can leave every decision unchanged. Field recovery is the field table. The overall row is one decision per file (fail if any rule fails): 18 files fail and 6 pass. The rule rows count 22 failing rule decisions, which is higher when a file fails more than one rule. Field exact match is 672 of 672 slots. 2 of those matches are slots that are empty in the label and empty in the extraction. Field precision and recall use a non-empty printed value as the positive class. A wrong non-empty value counts as both a false positive and a false negative.
<!-- eval-reading:end -->

<!-- eval-timing:start -->
Mean 0.4 ms per file (p50 0.3 ms, p95 1.0 ms) over 24 files.
<!-- eval-timing:end -->

The committed JSON (`reports/eval/report.json`) records mean 0.405 ms, p50 0.337 ms, p95 1.002 ms, max 1.626 ms, and 9.726 ms for all 24 files in one process. The max is the first file, which pays for pdfplumber opening its first document. A one-file CLI run in a fresh process is about 2 ms of pipeline time, which is what the sample commands above show.

That latency is machine time on small digital PDFs with a deterministic extractor. Classification metrics are deterministic; latency will move with the machine.

A perfect score on both tables means the deterministic extractor recovers both synthetic layouts, including hyphenated RFC/CURP strings, and the rules then replay the labels. The rule table alone does not show that recovery. This committed report does not measure LlamaParse or OpenAI. To point the same harness at another backend, pass `--parser` and `--extractor`. That report names the backends it actually scored, and it is not the committed no-key score.

## Design decisions

- **Two layouts, one schema.** Each document type is rendered in two label variants (for example `Fecha de inicio` and `Fecha de ingreso`, `Contrato laboral` and `Carta oferta`, `Nombre` and `Contribuyente`). The deterministic extractor accepts both. Unseen layouts are the job of the OpenAI extractor, which asks `chat.completions.parse` for the same Pydantic model.
- **Keys select the backend for `docval run`.** `LLAMA_CLOUD_API_KEY` selects LlamaParse (`POST /api/v2/parse/upload`, then poll `expand=text_full`). `OPENAI_API_KEY` selects structured extraction. Empty values count as unset. `docval eval` does not follow that switch: its default stays on the local parser and the deterministic extractor so the published score cannot change because a key happens to be in the environment. The LlamaParse client uses the standard library, so the optional parser does not add a required dependency.
- **Fail closed.** A missing name, RFC, CURP, issue date, contract start, or signature date fails the rule that needs it. The report says which field was missing. A document that never arrives does the same: the rules that needed its fields fail, and the report adds a warning that lists the missing documents.
- **Name policy.** Comparison ignores accents, case, punctuation, and the particles de/del/la/los/y. Surname-first order matches. A single initial may match the word it starts. An extra surname on only one side does not match. Token typos must be very close (ratio at least 0.92, and only for tokens of length 5 or more).
- **Contract dates.** The contract start must fall within `DOCVAL_CONTRACT_MAX_GAP_DAYS` of the agreed start (default 7 days). A gap equal to the limit passes; 8 days fails; the dataset's 30-day miss fails. The signature date must be present and on or before the start date. A contract with no signature date fails.
- **Address age.** The proof must be dated on or before the hire date and no more than 90 days earlier (`DOCVAL_ADDRESS_MAX_AGE_DAYS`). The dataset's hire date is 2026-10-01 for every case, so the window does not change when the calendar does. A bill dated in the future fails.
- **Synthetic identifiers.** Homoclaves and the CURP check character are deterministic stand-ins, not the official algorithms. Voter keys start with `SYN`. Every page carries `DOCUMENTO FICTICIO - SIN VALIDEZ OFICIAL`. A document that arrives without that banner is still reviewed, and the report adds a warning.
- **Labels stay out of the decision.** `application.json` is the only case metadata the pipeline reads. Defects live in `labels.json`.

## Layout

```text
src/docval/           library and CLI
  generate.py         seeded synthetic expedientes
  parsers.py          local PDF parser and LlamaParse client
  extractors.py       deterministic extractor and OpenAI extractor
  rules.py            the five review rules
  pipeline.py         parse, extract, review
  evaluate.py         precision, recall, accuracy, latency
  cli.py              docval generate | run | eval | serve
  api.py              FastAPI
data/golden/          24 committed cases, seed 42
reports/eval/         eval report from the run quoted above
reports/examples/     EXP-0001, EXP-0004, EXP-0008
tests/                pytest, including the no-key path
```

## Development

```bash
make test          # ruff + pytest, no API keys
make eval          # rewrite reports/eval on the no-key path
make generate      # rebuild data/golden with seed 42
docker build -t docval:local .
docker run --rm docval:local
```

CI is `.github/workflows/ci.yml`. It installs the `dev` extra on Python 3.11 and 3.12, runs Ruff (`ruff check` and `ruff format --check`), and runs pytest with `OPENAI_API_KEY` and `LLAMA_CLOUD_API_KEY` unset. It then runs `python -m docval run` and `python -m docval eval` with those keys blank, behind a proxy that rejects outbound HTTP, and checks that the report used the local parser and the deterministic extractor. A test reruns the eval and checks that classification metrics still match `reports/eval/report.json`, and that this README still quotes that report, including the note about what the 100% figures mean.

Configuration lives in `.env.example`. Thresholds are `DOCVAL_CONTRACT_MAX_GAP_DAYS` (default `7`) and `DOCVAL_ADDRESS_MAX_AGE_DAYS` (default `90`).

## Site

`site/` is the static page linked above. `.github/workflows/pages.yml` publishes it with GitHub Actions on every push to `main`, and `workflow_dispatch` can publish it by hand. The page loads `site/data/site.json`, written by:

```bash
python3 scripts/export_site_data.py
```

That file is built from `data/golden` and from `reports/eval/report.json`. `site/engine.js` is a line-by-line port of the deterministic extractor and of `src/docval/rules.py`. Check it against the Python results stored in `site.json`:

```bash
node site/check-engine.mjs
```

The page does not parse PDF bytes and does not call LlamaParse or OpenAI. `python -m docval run` remains the path that opens the PDFs. The typeface is Atkinson Hyperlegible (SIL Open Font License, Braille Institute), chosen because a reviewer reads an RFC and a CURP character by character and that face keeps 0, O, I, and l distinct. The only accent color is `#1C4E3A`, a flat stamp-ink green.

## License

MIT. Copyright (c) 2026 Edgar Flores. See [LICENSE](LICENSE).
