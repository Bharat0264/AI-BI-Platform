# AURA-BI final deployment report

**Status (2026-11-04): deployment package prepared; no live deployment verified from this workspace.**

## Frozen implementation baseline

- Branch: `research/independent-evaluation`
- Base committed revision: `b07a9ac15f9387d76756fcfb913fea621d34c8ea`
- Python: CPython 3.12.16
- Runtime dependencies: `requirements.txt`; dependency integrity check: `python -m pip check` reported no broken requirements.
- Regression run: 464 passed, 1 warning, 38.54 seconds, using the supported CPython environment. The single warning is the installed `google.generativeai` package's upstream deprecation warning; it is not a test failure.

This worktree contains uncommitted implementation and research artifacts. It must be committed in a reviewed release commit before a Git tag can truthfully identify the complete deployment candidate. A tag on the base revision alone would omit the research pipeline, report export, independent-evaluation infrastructure, and figure generator.

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

1. Commit the reviewed working tree and create an annotated release tag from that commit.
2. In Render, create/select a Python Web Service connected to that immutable commit.
3. Configure secret-managed `MONGODB_URI`, `MONGODB_DATABASE`, and a stable `AURA_SECRET_KEY` of at least 32 characters. Do not paste `.env` into source control.
4. Set `AURA_AUTH_REQUIRED=true`, `AURA_PUBLIC_DEMO=false`, `AURA_COOKIE_SECURE=true`; add custom domain hostnames to `AURA_TRUSTED_HOSTS` only if used.
5. Provision the first account privately with `python scripts/manage_user.py --username <operator>` against the same MongoDB database. Enter its password only at the terminal prompt.
6. Deploy and obtain the actual `onrender.com` or custom URL.
7. Run the live validation checklist in `docs/DEPLOYMENT_VALIDATION.md`; record only observed responses in `outputs/paper_evidence/deployment/`.

## Evidence and limitations

No hosting account authorization, Render service identifier, production MongoDB credentials, or live URL was available in this workspace. Therefore no live HTTP requests, uploads, screenshots, endpoint measurements, report downloads, or deployment performance records were created. Independent human benchmark evaluation is also still pending. Developer-only evidence remains separate from independent research results.

## Rollback

Use Render's deployment history to roll back to the previous known-good committed deployment. Do not rotate `AURA_SECRET_KEY` during routine rollback: rotation invalidates sessions and signed stored-dataset records.
