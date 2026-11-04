# Independent evaluation reproducibility and freeze procedure

1. Verify licenses/provenance and save an immutable source snapshot per dataset. Assign a dataset cluster and a question-template cluster before authoring questions.
2. Allocate entire clusters to development or evaluation. Never move a dataset family/template from development to evaluation after model/system tuning.
3. Produce `inputs.jsonl` with source checksums; keep all labels in restricted files. Obtain two independent annotations and an adjudication record per case.
4. Create `manifest.json` with external-human authorship, freeze timestamp, source/permission records, code commit, cluster split policy, and package SHA-256. Make the package read-only in the storage system used by the study.
5. Run `python -m benchmark.quality_control PACKAGE` and archive the JSON result. Then run `python -m experiments.independent_evaluation --package PACKAGE --output RESULTS.json`.
6. B0–B4 consume only case records/question fields supplied by `FrozenCase`; hidden labels are joined after execution. Apply the same timeout, memory limit, machine specification, and case order/seed policy to each. B5 remains `NOT RUN` unless a permitted fixed provider/model/version, prompt, access route, and cost logger are configured.

The quality-control command checks source hashes, label separation, annotation/adjudication completeness, duplicate normalized questions, development/evaluation cluster leakage, manifest checksum, and disagreement counts. It is not proof of human independence or label correctness.
