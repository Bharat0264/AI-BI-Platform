# Architecture

AURA-BI retains the Flask and vanilla-JavaScript product shell. Deterministic AURA services perform schema understanding, KPI discovery, analytical planning, visualization selection, AutoML, anomaly investigation, and evidence creation before optional LLM narration.

Persistence is accessed through PyMongo repositories. MongoDB is configured with `MONGODB_URI` and `MONGODB_DATABASE`; a single managed client pings at startup, creates required indexes, and records an idempotent schema version. Workspace is the ownership boundary for datasets, semantic corrections, analytics runs, evidence, ML runs, investigations, AI queries, and reports. Files remain external references.

Legacy SQLite is import-only through an explicit utility. The intermediate SQLAlchemy/PostgreSQL/Alembic layer was replaced before production migration.
