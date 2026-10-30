# Docval evaluation

Dataset `docval-golden-mx-onboarding` seed 42, 24 files.
Parser `local:pdfplumber`, extractor `deterministic`.
The positive class for precision and recall is a **fail** (a defect the reviewer should catch).
Contract start window 7 days. Address window 90 days.

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

<!-- field-table:start -->
| Document | Slots | Exact match | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| identificacion | 144 | 100.0% | 100.0% | 100.0% |
| constancia_fiscal | 144 | 100.0% | 100.0% | 100.0% |
| comprobante_domicilio | 192 | 100.0% | 100.0% | 100.0% |
| contrato | 192 | 100.0% | 100.0% | 100.0% |
| all fields | 672 | 100.0% | 100.0% | 100.0% |
<!-- field-table:end -->

<!-- eval-timing:start -->
Mean 0.4 ms per file (p50 0.3 ms, p95 1.0 ms) over 24 files.
<!-- eval-timing:end -->

No disagreements between the pipeline and the golden labels.
