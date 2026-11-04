# Experimental readiness report — external evaluation

Status: **annotation infrastructure ready; publication experiment not ready to execute.**

Lifecycle correction: SIIE impact diagnostics were formerly counted as report-candidate exclusions alongside conditional candidates. They are now persisted as `INTERPRETATION_IMPACT_DIAGNOSTIC`, remain unresolved and inspectable, and are excluded from report selection/accounting. Conditional candidate evidence remains unresolved and is never selected as a business conclusion. See [evidence lifecycle analysis](EVIDENCE_LIFECYCLE_ANALYSIS.md).

The baseline runner accepts `FrozenCase` objects containing only `case_id`, source records, question, dataset ID, dataset cluster, and template cluster. Labels remain separately loaded and are joined after each baseline response. B0–B4 can therefore be invoked on frozen external inputs without direct label access. Their comparability still depends on a predeclared runtime/memory budget and frozen package, neither of which has yet been supplied. B1/B2 remain simplified deterministic baselines and B3/B4 share some implementation; this must be stated in future findings.

B5 is **NOT RUN**. No permitted fixed-model credential, model/version declaration, prompt registry, or cost capture configuration is present.

No public data source is currently claimed verified by this repository. The six-domain registry is only a procurement template. No human annotations, adjudications, external cases, baseline measurements, figures, or statistical comparisons were generated.

## IEEE checklist update

- [x] Python 3.12.16 regression environment prepared; lifecycle/research/authentication/security/browser group: 83 passed.
- [x] Blind two-annotator/adjudicator templates and package validation implemented.
- [x] External input/hidden-label separation and frozen checksums implemented.
- [ ] Licensed source snapshots and verified provenance for all domains.
- [ ] Independent annotation, disagreement analysis, adjudication, and frozen corpus.
- [ ] Matched B0–B4 traces; permitted B5 execution or justified exclusion.
- [ ] Predeclared resource budgets, metrics, cluster-aware analysis, measured figures/tables.
- [ ] Completed clean full-suite artifact after lifecycle correction. A full rerun was initiated but the execution service did not return its terminal report; do not infer a clean suite from partial output.

The manuscript is not submission-ready.
