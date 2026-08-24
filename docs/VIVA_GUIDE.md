# Viva Guide

Production persistence uses MongoDB through PyMongo, selected by `MONGODB_URI` and `MONGODB_DATABASE`. Lightweight schema versioning and idempotent indexes replace Alembic; SQLite is only a legacy import path.

AURA-BI autonomously interprets business schemas, selects deterministic analytics, stores traceable evidence, and optionally uses Gemini only to explain computed evidence. The product UI exposes evidence for analyst answers, saved model runs, and diagnostic root-cause decompositions. Contributions and anomalies are framed as associations, not causal effects. It differs from NEXORA-CDI: AURA-BI does not estimate treatments, counterfactuals, calibrated decision confidence, decision gates, or causal provenance.
