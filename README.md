# AURA-BI

**Autonomous Unified Reasoning & Analytics for Business Intelligence**

> *AURA-BI: A Self-Adaptive Multi-Agent Framework for Autonomous Business Intelligence over Heterogeneous Enterprise Data*

AURA-BI is an evidence-first business intelligence platform that understands unfamiliar datasets, infers business semantics, proposes valid KPIs and visualizations, plans deterministic analytics, investigates anomalies, supports practical AutoML, and answers business questions without allowing an LLM to invent metrics. It preserves the existing responsive dashboard and its established sales analytics, forecasting, voice interaction, reporting, and workspace features.

## What is implemented

- CSV, XLSX, and JSON ingestion with preserved original uploads and legacy SQLite connector support.
- Deterministic dataset profiling: types, null rate, unique counts, duplicates, numeric statistics, correlations, and quality warnings.
- Semantic Business Schema Engine with role, confidence, evidence, and persisted user corrections.
- Adaptive KPI discovery only when required semantic fields are present.
- Structured Analytics Planner and visualization recommendations.
- Verified natural-language analytics: question → plan → pandas computation → `AnalyticsEvidence` → optional Gemini evidence narration.
- Safe unsupported-question response: `INSUFFICIENT DATA`.
- Isolation Forest diagnostic anomaly evidence and guarded supervised AutoML with reproducible splits, metrics, and feature importance.
- Existing executive dashboard, filters, Plotly charts, six-month forecast/planning, browser voice interface, PDF report, saved dashboards, alerts, actions, schedules, and stock-analysis tools.
- AURABench starter synthetic retail generator and reproducible experiment smoke runner.
- Phase 2 workspaces for Data Intelligence, Analytics, AutoML, Anomaly Intelligence, AI Analyst evidence, and research status, all inside the existing UI.

## Architecture

```text
Original enterprise data
  → profile + semantic schema
  → KPI / planner / visualization / anomaly / ML services
  → AnalyticsEvidence
  → optional provider-backed explanation
  → existing Flask API and dashboard
```

The specialized Data, Analyst, ML, Anomaly, Visualization, and Report services exchange structured outputs through an orchestrator. Computation is deterministic first; LLM use is optional and constrained to supplied evidence.

## Run locally

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python server.py
```

Open `http://127.0.0.1:5000`. Gemini is optional; set `GEMINI_API_KEY` in `.env` only to enable evidence-grounded phrasing. The UI remains unchanged; AURA services are available through `/api/aura/inspect`, `/api/aura/schema`, `/api/aura/ml`, and the upgraded `/api/ask`.

Run checks:

```powershell
python -m pytest tests -q
python experiments/run_all.py --seed 42
```

For test tooling, install `requirements-dev.txt` and run `python -m pytest tests -q`.

## Research boundaries

AURA-BI supports autonomous analytics and semantic business intelligence. It does **not** make causal claims: correlations, contribution slices, anomalies, and feature importance/SHAP are diagnostic, not causal evidence.

It is distinct from **NEXORA-CDI**, which focuses on causal inference, treatment-effect estimation, counterfactual decisions, calibrated decision confidence, decision gates, and decision provenance.

See [architecture](docs/ARCHITECTURE.md), [project specification](docs/PROJECT_SPEC.md), [methodology](docs/RESEARCH_METHODOLOGY.md), [experiment guide](docs/EXPERIMENT_GUIDE.md), [viva guide](docs/VIVA_GUIDE.md), and the [current-system audit](docs/CURRENT_SYSTEM_AUDIT.md).

## Deployment

The existing Render/Waitress configuration remains compatible. Configure `GEMINI_API_KEY` only when optional evidence narration is required.

## Persistence

MongoDB is AURA-BI's primary persistent database. Copy `.env.example`, set secret-managed `MONGODB_URI` and `MONGODB_DATABASE`, then run `python scripts/init_mongodb.py`. See [persistence architecture](docs/PERSISTENCE_ARCHITECTURE.md) for the optional legacy SQLite-import workflow.

For Render + MongoDB Atlas deployments, allow the Render service's outbound network in Atlas Network Access and use the Atlas Driver URI exactly (percent-encoding reserved password characters). AURA-BI validates Atlas TLS certificates with Certifi; do not disable certificate validation. See the deployment troubleshooting notes in [persistence architecture](docs/PERSISTENCE_ARCHITECTURE.md).
