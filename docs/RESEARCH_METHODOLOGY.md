# Research Methodology

## Implemented experimental design

Evaluate AURABench families with ground-truth roles, KPIs, analytical tasks, answerability labels, source columns and injected anomalies. Compare B0 static analytics, B1 direct-LLM context only when explicitly configured, B2 semantic-only analytics, B3 evidence AURA, B4 full verifier-driven AURA-BI, and flag-driven component ablations. Report role accuracy, macro/per-role precision/recall/F1, KPI precision/recall/F1, answerability, task accuracy, tolerance-aware numerical correctness, Supported Claim Rate, Unsupported Numerical Claim Rate, anomaly F1, latency and repair frequency.

C1 fuses normalized names, type/numeric coverage, cardinality, uniqueness, date parseability and distribution cues; confirmed workspace corrections remain authoritative. C2 maps each numerical claim to a dataset, source columns, filters, operation, deterministic result and `AnalyticsEvidence`. C3 runs deterministic verification and permits at most two repairs; unsupported output becomes `INSUFFICIENT DATA`. C4 evaluates the same ground truth through seeded schema perturbations.

## Measured versus proposed

The framework and metrics are implemented. Scores exist only in generated experiment outputs and are not research conclusions until a run is executed and reported. Statistical summaries provide mean, standard deviation, 95% normal-approximation confidence intervals and sample counts. No causal interpretation or superiority claim is made by this methodology.
