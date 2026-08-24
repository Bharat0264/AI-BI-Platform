# Architecture

Persistence is accessed through SQLAlchemy repositories. PostgreSQL is selected with `DATABASE_URL`; the existing SQLite database remains the local compatibility default. Alembic migrations and the normalized AURA artifact schema are documented in `docs/PERSISTENCE_ARCHITECTURE.md`.

AURA-BI keeps the Flask/vanilla-JS product shell. `aura/` is the application-service layer: schema/profile → KPI/planner/visualization/anomaly/ML → `AnalyticsEvidence` → optional Gemini evidence narration. Existing sales dashboard and forecast services remain available in `app/`; `/api/ask` uses AURA’s evidence-first route. The UI exposes Data Intelligence, Analytics, AutoML, Anomaly Intelligence, AI Analyst, Reports, and Research within the existing sidebar shell. SQLite persists schema corrections and run history. `/api/aura/analytics`, `/api/aura/root-cause`, and `/api/aura/history` exchange structured evidence with those workspaces.
