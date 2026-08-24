# AURA-BI Engineering Rules

- Keep the existing Flask/vanilla-JS UI unless a UI change is explicitly requested.
- Preserve uploaded source data; cleaning produces a derived copy/configuration.
- Compute evidence before narrative generation. LLM providers receive compact evidence, not raw CSVs.
- Treat correlation, feature importance, SHAP, anomaly slices, and contributions as non-causal.
- Reject unsupported analytical questions with `INSUFFICIENT DATA`.
- Use deterministic heuristics before optional LLM assistance; user semantic corrections are authoritative.
- Do not hard-code benchmark or model results. Run only reproducible experiments.
