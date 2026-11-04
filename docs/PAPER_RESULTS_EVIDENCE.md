# Paper results evidence package

Run `python -m experiments.paper_evidence_export` from the repository root. It writes actual, reproducible **developer-only** artifacts under `outputs/paper_evidence/`.

The package separates: (1) UCI source summaries; (2) deterministic developer correctness, ambiguity, EVVE, dashboard, and timing records; (3) missing-evidence declarations; and (4) provenance. PNG figures are 300 DPI and each has CSV/JSON source tables. No figure is produced for independent baselines, ablations, or deployment performance because the required evidence does not exist.

The timing fixture is a 1,000-row non-mutating developer-derived slice of UCI Online Retail. It records ten sequential `perf_counter_ns` measurements per component and process maximum RSS. It is not a scalability benchmark or independent evaluation. The generated developer gross/net fields are explicitly synthetic transformations for grammar/ambiguity testing, not a claim about the source business definitions.
