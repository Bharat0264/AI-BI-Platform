# AURA-BI final deployment report

**Status (2026-11-04): live availability partially validated; authenticated research workflow not yet validated.**

The live URL `https://aura-bieee.onrender.com` served the homepage over certificate-verified HTTPS. `GET /api/health` returned `200` and `{"persistence":"mongodb","status":"ready"}`. `GET /api/auth/session` reported `auth_required=true` before login, and ten unauthenticated requests to `/api/research/dashboard` returned `401`. The service does not expose a commit/version identifier, and no Render deploy log/service access was supplied, so the deployed commit cannot be independently confirmed from this workspace.

Thirty controlled requests are recorded in `outputs/paper_evidence/deployment/measurements.csv`; their summaries are in `performance_summary.csv`. They measure endpoint availability and authentication enforcement only. They do not establish research-pipeline performance or correctness.

## Frozen implementation baseline

- Branch: `research/independent-evaluation`
- Frozen implementation revision: `e08143c50455e3e0aa1783f78bd0ec7ffc22620c`
- Python: CPython 3.12.16
- Runtime dependencies: `requirements.txt`; dependency integrity check: `python -m pip check` reported no broken requirements.
- Regression run: 464 passed, 1 warning, 38.54 seconds, using the supported CPython environment. The single warning is the installed `google.generativeai` package's upstream deprecation warning; it is not a test failure.

The frozen implementation revision contains the reviewed research pipeline, report export, independent-evaluation infrastructure, and figure generator. The accompanying release metadata is committed separately; the annotated release tag identifies the complete snapshot.

## Included implemented components

- Flask/vanilla-JS application with account-scoped dataset storage.
- Deterministic semantic analytics, numerical evidence verification, and provenance.
- Semantic Interpretation Impact Engine (SIIE).
- Evidence-Verified Visualization Engine (EVVE).
- Dashboard semantic consistency checks and selective publication gate.
- Opt-in `/api/research/dashboard` and `/api/research/report` contracts.
- Evidence-verified PDF generation and adjacent JSON provenance manifest.
- Independent-benchmark collection, annotation, adjudication, and freeze safeguards.

## Deployment profile

The checked-in Render Blueprint now specifies private authenticated mode:

- build: `python -m pip install -r requirements.txt`
- start: `python start.py`
- health: `GET /api/health`
- WSGI server: Waitress, binding Render's `0.0.0.0:$PORT`
- TLS: Render terminates HTTPS; the server sets the known external HTTPS scheme only for Render.
- account mode: `AURA_AUTH_REQUIRED=true`, `AURA_PUBLIC_DEMO=false`, secure cookies required.

Render is compatible with the one-service architecture: Flask serves static frontend assets and APIs, while MongoDB stores account-scoped data. It supports HTTPS and HTTP health checks. Its standard filesystem is ephemeral; PDFs are streamed to the requester. Configure an operator-owned persistent disk and `AURA_REPORT_DIR` only if report retention is required; the application otherwise labels the storage mode `ephemeral_local`.

## Required operator actions before a live deployment

1. In Render, create/select a Python Web Service connected to the annotated release tag.
2. Configure secret-managed `MONGODB_URI`, `MONGODB_DATABASE`, and a stable `AURA_SECRET_KEY` of at least 32 characters. Do not paste `.env` into source control.
3. Set `AURA_AUTH_REQUIRED=true`, `AURA_PUBLIC_DEMO=false`, `AURA_COOKIE_SECURE=true`; add custom domain hostnames to `AURA_TRUSTED_HOSTS` only if used.
4. Provision the first account privately with `python scripts/manage_user.py --username <operator>` against the same MongoDB database. Enter its password only at the terminal prompt.
5. Deploy and obtain the actual `onrender.com` or custom URL.
6. Run the live validation checklist in `docs/DEPLOYMENT_VALIDATION.md`; record only observed responses in `outputs/paper_evidence/deployment/`.

## Evidence and limitations

A live URL was supplied and non-destructive public endpoint checks were completed. Render service/log access and private test-account credentials remain unavailable. Therefore no authenticated uploads, analytical answers, chart contracts, report downloads, dataset-isolation checks, screenshots, or research-pipeline timings have been created. Independent human benchmark evaluation is also still pending. Developer-only evidence remains separate from independent research results.

## Rollback

Use Render's deployment history to roll back to the previous known-good committed deployment. Do not rotate `AURA_SECRET_KEY` during routine rollback: rotation invalidates sessions and signed stored-dataset records.
