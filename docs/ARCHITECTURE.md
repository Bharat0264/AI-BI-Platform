# Architecture

AURA-BI retains the Flask and vanilla-JavaScript product shell. Deterministic AURA services perform schema understanding, KPI discovery, analytical planning, visualization selection, AutoML, anomaly investigation, and evidence creation before optional LLM narration.

Persistence is accessed through PyMongo repositories. MongoDB is configured with `MONGODB_URI` and `MONGODB_DATABASE`; a single managed client pings at startup, creates required indexes, and records an idempotent schema version. Workspace is the ownership boundary for datasets, semantic corrections, analytics runs, evidence, ML runs, investigations, AI queries, and reports. Files remain external references.

Legacy SQLite is import-only through an explicit utility. The intermediate SQLAlchemy/PostgreSQL/Alembic layer was replaced before production migration.
## Research modules

`benchmark/` produces typed, seeded AURABench examples and ground truth. `benchmark/perturbations/` changes only schema presentation. `aura/provenance.py` emits evidence-linked claims; `aura/verifier.py` verifies numerical claims against deterministic evidence. `experiments/` runs baseline and ablation configurations and emits raw records, tables and figures. These modules sit beside the existing Flask/UI/MongoDB path and do not replace it.
