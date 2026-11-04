# Prespecified external-evaluation configuration (v1, before collection)

- Runtime: CPython 3.12.16; dependencies from `requirements-dev.txt` with `constraints-local-win-py312.txt`; record `pip freeze`, OS, CPU model, RAM and git commit.
- Splits: assign whole `dataset_cluster` and `template_cluster` values to development or evaluation before annotation. The frozen evaluation manifest may not overlap either development set.
- Per case: one cold run and two warm repetitions per baseline after a fixed process warm-up; random order generated from and recorded with seed 20261104; report all individual traces, median latency and maximum RSS. No response cache may cross cases, baselines, or split boundaries; within-run deterministic evidence cache must be logged.
- Limits: 30 s wall-clock and 1 GiB RSS per case; timeout, memory breach, exception, or unsupported request is a recorded outcome, never dropped. Apply identical limits to B0–B4.
- Baselines: B0 fixed/manual convention; B1 first admissible candidate; B2 clarification-only; B3 deterministic semantic/numerical verification without visualization verification; B4 full pipeline. Record shared code/components and capability differences; do not call them independent implementations where they share code.
- B5: NOT RUN unless a permitted fixed provider/model revision, credential path, prompt registry, cost accounting and budget are frozen before execution.
- Primary metric: unsafe unconditional-answer rate, with denominator all cases whose adjudicated contract requires clarification/refusal. Report it jointly with answerable coverage.
- Secondary metrics: candidate precision/recall/F1; numerical correctness; visualization validity; dashboard precision/recall; correct refusal; verified-evidence coverage; latency; RSS; clarification overhead; failure categories.
- Analysis: paired case-level differences with dataset/template-cluster-aware bootstrap confidence intervals only after enough independent clusters. Treat no rows from one source/template as independent for inference; otherwise report descriptive estimates and explicit `NOT_RUN` inference.
