# MongoDB Persistence Architecture

## Current architecture

AURA-BI uses PyMongo and MongoDB as its primary persistent database. A single managed `MongoClient` is configured through `MONGODB_URI` and `MONGODB_DATABASE`; startup pings MongoDB, ensures indexes, and records schema version 1 in `schema_versions`. The application exposes stable UUID-style application IDs rather than Mongo ObjectIds.

Collections: `workspaces`, `datasets`, `dataset_profiles`, `semantic_schemas`, `analytics_runs`, `analytics_evidence`, `ml_runs`, `anomaly_investigations`, `ai_queries`, `reports`, and `schema_versions`. Legacy workspace records/settings are mapped into `legacy_records` and `settings` for API compatibility.

MongoDB fits AURA-BI because profiles, semantic metadata, evidence results, root-cause slices, and ML configurations have valid but variable nested shapes. This is a workload fit, not a claim that MongoDB is universally superior to relational databases. Uploaded data, model artifacts, and PDFs remain file references rather than database blobs.

## Operations

```powershell
$env:MONGODB_URI = "mongodb+srv://USER:PASSWORD@HOST/"
$env:MONGODB_DATABASE = "aura_bi"
python scripts/init_mongodb.py
python server.py
python -m pytest tests -q
```

Run `python scripts/migrate_sqlite_to_mongodb.py data/platform.db --dry-run` before an optional legacy import. It safely reads the old SQLite records/settings, preserves IDs where possible, skips duplicates, and never runs automatically.

The SQLAlchemy/PostgreSQL/Alembic implementation was an intermediate development architecture and was replaced before production data migration.
