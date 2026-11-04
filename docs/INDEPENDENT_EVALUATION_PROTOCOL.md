# Independent evaluation and annotation protocol

Status: infrastructure implemented; no external human-authored corpus has been collected or scored.

## Boundary

`benchmark/evaluation.py` contains Codex/developer-authored stress fixtures. They are development data, even where earlier code called them “heldout.” They must not be presented as independent validation, used for significance tests, or mixed with the frozen corpus below.

An independent corpus is a directory containing `manifest.json`, `inputs.jsonl`, `labels.jsonl`, `annotators.jsonl`, and `adjudications.jsonl`. Inputs are the only files given to a system. Labels are joined after execution by `experiments.independent_evaluation`; the loader rejects inputs containing label-like fields.

## Required frozen manifest

`manifest.json` must state `authorship: "external_human"`, a UTC `frozen_at`, corpus version, license/permission, source provenance, code commit, split policy, and SHA-256 manifest of each input snapshot. Split by `dataset_family` *and* `template_family`; neither may appear in development and evaluation sets. Each `inputs.jsonl` row carries a SHA-256 of canonical JSON `records`; changing a row invalidates the package.

## Annotation workflow

1. Before cases are visible to developers, an external curator samples licensed, non-sensitive source tables from at least three domains and allocates source datasets and question templates to development or evaluation.
2. Two annotators independently inspect each assigned source snapshot and question. They do not inspect AURA output. They label: answerability; all admissible candidate definitions and source columns; requested aggregate/group/ranking/difference values; currency/unit compatibility; valid chart types/specification; provenance verification expectation; and dashboard consistency/conflict categories.
3. A separate adjudicator resolves disagreement without changing the immutable source input. The adjudication record cites competing annotation IDs and a rationale. Keep disagreement rather than overwriting it.
4. Freeze hashes, identities/pseudonyms, annotation-tool version, timestamp, and exclusion reasons. Only then allow experiment execution.

Required label categories cover semantic ambiguity, KPI-definition conflict, equal totals/different breakdowns, ranking reversal, invalid visualization specifications, cross-dashboard inconsistency, missing/incompatible units, unsupported questions, dataset-version change, and provenance/evidence failure.

## JSONL contracts

Input rows require `case_id`, `dataset_id`, `dataset_family`, `template_family`, `records`, `question`, and `source_sha256`. They must contain no expected answer or label.

Label rows require `case_id`, `answerability`, `candidate_definitions`, `numerical_oracle`, `visualization_label`, `dashboard_label`, `provenance_label`, and `adjudication_id`. Candidate definitions record business term, column(s), formula, unit/currency, and whether admissible. Numerical values must be independently calculated (e.g., spreadsheet/Decimal oracle) with methodology recorded.

Annotator rows require `annotation_id`, pseudonymous `annotator_id`, training version, case ID, timestamp, and all labels. Adjudications require `adjudication_id`, case ID, both independent annotation IDs, adjudicator ID, decision, rationale, and timestamp. Do not record personal data beyond approved study metadata.

## Execution and reporting

Run `python -m experiments.independent_evaluation --package PATH --output RESULT.json`. With no valid package, the result is `NOT_RUN`; the runner never falls back to synthetic cases. Run B0–B4 on exactly the same inputs and declared time/memory budget; B5 is `NOT_RUN` unless fixed provider/model/version, access, cost recording, and permissions are configured. Preserve raw traces, seeds, dependency versions, package hash, failures, denominators, and resource readings.

Report interpretation precision/recall/F1, numerical correctness, visualization validity, dashboard detection precision/recall, unsafe unconditional answers, correct refusal, answerable coverage, evidence coverage, latency, memory, and clarification overhead. Accuracy and coverage must be reported together. Use paired dataset/template-cluster analysis only after enough independent clusters; the included helper explicitly refuses fewer than three paired dataset clusters.

## External work still required

- Recruit/train independent annotators and an adjudicator.
- Obtain licensed, non-sensitive source data and documented provenance.
- Collect, double-label, adjudicate, checksum, and freeze the corpus.
- Establish pre-registered budgets, scoring rules, and a cluster-aware analysis plan.
- Execute B0–B5 where permitted; B5 remains optional and must never be simulated.
