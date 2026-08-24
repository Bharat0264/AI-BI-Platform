# Persistence Architecture

## Audit and migration

Phase 2 stored workspace settings and generic UI records in `data/platform.db` using raw SQLite. Active data is preserved as a local pickle; reports and models are files, not database blobs. Semantic corrections, run history, AI history, and investigations were JSON payloads in `records`.

Phase 3 retains the compatible `platform_store` API but backs it with SQLAlchemy. `DATABASE_URL` selects PostgreSQL (`postgresql+psycopg://...`) or, by default, the existing SQLite database. The normalized schema adds workspace, dataset/profile, semantic-column, analytics-run/evidence, ML-run, anomaly-investigation, AI-query, and report entities. Source files and model artifacts remain filesystem references.

## Operations

```powershell
$env:DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/aura_bi"
python -m alembic upgrade head
python server.py
python -m pytest tests -q
```

Use `python scripts/migrate_sqlite_to_postgres.py data/platform.db --dry-run` before an optional import. The utility only copies legacy records/settings, skips existing IDs, and never runs automatically. Test migrations against an isolated URL; never run downgrade against an unknown production database.
