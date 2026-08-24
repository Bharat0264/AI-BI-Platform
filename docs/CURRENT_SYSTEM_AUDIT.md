# Current System Audit — AURA-BI Migration

Audit date: 2026-08-25.

## Existing system

The repository is a Flask 3.1 application serving a responsive vanilla HTML/CSS/JavaScript interface.  It is not a Streamlit application.  `server.py` owns the REST endpoints and orchestrates Pandas-based analytics; `app/` contains normalization, forecasting, charts, reports, voice helpers, and Gemini integration. SQLite (`platform_store.py`) persists workspace records and settings. Render/Waitress deployment is configured.

| Area | Status | Migration decision |
| --- | --- | --- |
| CSV/XLSX/JSON upload | Working | Reuse; retain source pickle and add non-mutating profile artifacts. |
| Dataset normalization | Working for sales-oriented data | Retain for legacy dashboard; add general semantic inference before planning. |
| KPIs/charts/EDA | Working, sales-schema-specific | Preserve UI output; add adaptive KPI/visualization services. |
| Forecasting | Working practical baseline | Preserve as the legacy forecast path; expose task inference for broader ML. |
| Gemini Q&A | Present, but sends a raw data sample | Replace endpoint flow with evidence-first provider abstraction. |
| Voice | Browser speech recognition/TTS UI | Preserve; it continues to call `/api/ask`. |
| PDF reporting | Working ReportLab report | Preserve; future evidence records can populate it. |
| Persistence | SQLite records/settings | Reuse for workspace metadata and semantic corrections; PostgreSQL/Alembic remains an optional production migration. |
| Tests | No focused automated suite found | Add deterministic pytest coverage. |

## Reuse and risks

The current UI, filtering, Plotly views, report download, and forecasting are retained. The largest risk is that existing `prepare_dataset` requires a date and sales-like field, while AURA-BI must accept heterogeneous datasets. New services therefore operate on the original uploaded DataFrame and the legacy dashboard continues to use normalization. Gemini availability is optional and never required for deterministic results. Existing SQLite records are not migrated destructively.
