# AURA-BI

**Autonomous Unified Reasoning & Analytics for Business Intelligence**

> *AURA-BI: A Self-Adaptive Multi-Agent Framework for Autonomous Business Intelligence over Heterogeneous Enterprise Data*

AURA-BI is an evidence-first business intelligence platform that understands unfamiliar datasets, infers business semantics, proposes valid KPIs and visualizations, plans deterministic analytics, investigates anomalies, supports practical AutoML, and answers business questions without allowing an LLM to invent metrics. It preserves the existing responsive dashboard and its established sales analytics, forecasting, voice interaction, reporting, and workspace features.

Render startup/cache-recovery follow-up: **405 tests passed**. See [deployment setup](docs/RENDER_DEPLOYMENT.md) and [measured startup validation](docs/validation/render-startup.json). Earlier phase results below are historical snapshots.

## Latest verification

On 2 November 2026, the fresh Python 3.12.16 environment passed **395 tests**, including **22 browser checks**, and its dependency audit found **no known vulnerabilities**. Arithmetic/language/scope evaluations passed **332/332**, **154/154**, and **70/70**. Public-data validation passed **29/32**; the remaining three opaque-column cases require explicit semantic confirmation. See [measured records and limits](docs/validation/summary.json). These checks do not establish production readiness or competitive superiority.

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
- AURABench: eight seeded heterogeneous synthetic data families, preserved ground truth, schema perturbations, baselines, ablations, metrics, raw records, and publication-readable figure generation.
- Claim-level provenance, deterministic evidence verification, and a bounded verify-and-repair loop for numerical analytical responses.
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

## Release status

Account login, per-user storage isolation and security-patched Python 3.12 dependencies are implemented. The launcher supports local evaluation and **authenticated Render hosting**. Render requires a private signing secret, secure cookies and configured MongoDB; see [Render setup](docs/RENDER_DEPLOYMENT.md). Production infrastructure validation remains an operator responsibility. No live service settings have been changed by editing this repository.

## Run locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints-local-win-py312.txt
Copy-Item .env.example .env
# Set isolated MongoDB credentials and AURA_SECRET_KEY in .env before proceeding.
.\.venv\Scripts\python.exe scripts/manage_user.py --username analyst@example.com
.\.venv\Scripts\python.exe start.py
```

Open `http://127.0.0.1:10000`. The constraints file records the tested Windows/Python 3.12 environment; it is not a cross-platform production lock. See [account security and operator setup](docs/ACCOUNT_SECURITY.md) for account provisioning, sessions and storage isolation. Do not overwrite an existing .env. MongoDB is required. Gemini narration is optional and disabled by default. The source-only archive excludes demo/uploaded data; import a dataset through the UI.

Run checks:

```powershell
python -m pytest tests -q
python experiments/run_all.py --mode smoke --seed 42
python experiments/run_all.py --mode small --seed 42
```

For test tooling, install `requirements-dev.txt` and run `python -m pytest tests -q`.

## Research boundaries

AURA-BI supports autonomous analytics and semantic business intelligence. It does **not** make causal claims: correlations, contribution slices, anomalies, and feature importance/SHAP are diagnostic, not causal evidence.

It is distinct from **NEXORA-CDI**, which focuses on causal inference, treatment-effect estimation, counterfactual decisions, calibrated decision confidence, decision gates, and decision provenance.

See [architecture](docs/ARCHITECTURE.md), [project specification](docs/PROJECT_SPEC.md), [methodology](docs/RESEARCH_METHODOLOGY.md), [experiment guide](docs/EXPERIMENT_GUIDE.md), [viva guide](docs/VIVA_GUIDE.md), and the [current-system audit](docs/CURRENT_SYSTEM_AUDIT.md).

Research execution details: [AURABench](docs/AURABENCH.md) and [reproducibility](docs/REPRODUCIBILITY.md). Generated experiment files are measurements from the current run, not committed publication claims.

## Deployment

On Render, use `python start.py`. The launcher binds `0.0.0.0:$PORT`, forces authenticated hosting and uses HTTPS-aware session/origin handling behind Render’s TLS edge. The blueprint declares required account/MongoDB settings and keeps auto-deploy off. Existing services must update their own settings/environment; a repository blueprint does not automatically configure them. See [Render deployment and cache recovery](docs/RENDER_DEPLOYMENT.md).

## Persistence

MongoDB is AURA-BI's primary persistent database. Copy `.env.example`, set secret-managed `MONGODB_URI` and `MONGODB_DATABASE`, then run `python scripts/init_mongodb.py`. See [persistence architecture](docs/PERSISTENCE_ARCHITECTURE.md) for the optional legacy SQLite-import workflow.

For Render + MongoDB Atlas deployments, allow the Render service's outbound network in Atlas Network Access and use the Atlas Driver URI exactly (percent-encoding reserved password characters). AURA-BI validates Atlas TLS certificates with Certifi; do not disable certificate validation. See the deployment troubleshooting notes in [persistence architecture](docs/PERSISTENCE_ARCHITECTURE.md).


## Answer definitions and lifecycle

The deterministic question API supports conditional column interpretations, explicitly confirmed versioned defaults, and dependency freshness with reviewed recomputation. The AI Analyst interface provides interpretation choices, confirmed definitions, freshness indicators, version history and reviewed recalculation. See the [interface guide](docs/ANALYST_INTERFACE.md) for the user flow and browser-test instructions. See [interpretation checks](docs/INTERPRETATION_CHECKS.md), [saved definitions](docs/SAVED_DEFINITIONS.md), and [artifact lifecycle](docs/ARTIFACT_LIFECYCLE.md) for request formats and limits.


For independent analyst arithmetic and coverage checks, run `python experiments/accuracy.py`. See the [evaluation results and limits](docs/ACCURACY_EVALUATION.md); synthetic regression success is not real-world validation.


The analyst accepts common total/average/grouped-ranking phrasing through a whole-question typed grammar. See [supported question forms and evaluation](docs/QUESTION_PARSING.md). Unknown filters and time qualifiers still fail explicitly.


The analyst also supports explicit region/category filters and calendar-period comparisons through its scope controls or API. See [scoped analytics](docs/SCOPED_ANALYTICS.md) for date boundaries, replay behavior and limits. Validate row selection and calculations with `python experiments/accuracy.py --suite scope`.


Public real-data validation and its remaining cold-start gaps are documented in [real-data validation](docs/REAL_DATA_VALIDATION.md). General datasets can be imported for AURA without fabricated financial metrics, and source date formats can be declared explicitly in scope controls. Fetching the pinned public validation data is an optional, explicit step.

Phase 10 local security hardening and performance results, including unresolved release gates: [Security and performance](docs/SECURITY_PERFORMANCE.md).

Phase 11 interface changes and browser validation: [Usability and polish](docs/USABILITY_POLISH.md).

Final completion adds [account security](docs/ACCOUNT_SECURITY.md), a fresh Python 3.12 installation and audit, and pinned GitHub Actions regression/security workflows. Earlier phase reports are historical snapshots; their missing-authentication/shared-data findings are superseded by this implementation. Hosted deployment and real infrastructure validation are still separate release gates.
