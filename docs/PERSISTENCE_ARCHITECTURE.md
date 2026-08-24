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

## Render and Atlas TLS troubleshooting

Configure `MONGODB_URI` with Atlas's driver connection string and `MONGODB_DATABASE` in Render's secret environment settings. The client uses Certifi's CA bundle and keeps TLS certificate validation enabled. Do not set `tlsAllowInvalidCertificates=true` to work around connection errors.

An Atlas TLS handshake error is normally an environment/connectivity issue rather than an application-data issue. Before redeploying, verify:

- Atlas **Network Access** permits the Render service's outbound IP range. On Render plans with dynamic egress, a temporary `0.0.0.0/0` Atlas rule may be required for diagnosis; restrict it or use static egress/private connectivity for production.
- The value contains no surrounding quotes or line breaks, and any reserved password characters are percent-encoded.
- The Atlas cluster is running and the URI was copied from **Connect → Drivers** for that cluster.

Optional timeout environment variables are in milliseconds: `MONGODB_SERVER_SELECTION_TIMEOUT_MS` (default `15000`), `MONGODB_CONNECT_TIMEOUT_MS` (default `10000`), and `MONGODB_SOCKET_TIMEOUT_MS` (default `20000`).
