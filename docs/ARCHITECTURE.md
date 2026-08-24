# Architecture

AURA-BI keeps the Flask/vanilla-JS product shell. `aura/` is the new application-service layer: schema/profile → KPI/planner/visualization/anomaly/ML → `AnalyticsEvidence` → optional Gemini evidence narration. Existing sales dashboard and forecast services remain available in `app/`; `/api/ask` now uses AURA’s evidence-first route. SQLite persists workspace records and user schema corrections; a future PostgreSQL/Alembic adapter can replace this store without changing service contracts.
