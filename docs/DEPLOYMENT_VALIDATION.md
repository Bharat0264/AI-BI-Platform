# Deployment validation — pending operator authorization

Status: **PARTIALLY VALIDATED LIVE SERVICE**. On 2026-11-04, `https://aura-bieee.onrender.com` returned homepage `200`, `/api/health` returned `200` with MongoDB `ready`, and the unauthenticated session endpoint reported `auth_required=true`. The protected research-dashboard endpoint returned `401` for every unauthenticated controlled request. No Render operator session, deployed-log access, or private test-account credentials were supplied; therefore the deployed commit, authenticated analytics, report export, dataset isolation, and screenshots remain unverified.

Observed raw-safe records and timing summaries are in `outputs/paper_evidence/deployment/`. These are deployment engineering observations, not independent research evaluation.

## Audited architecture

One Python 3.12.16 Render web service is sufficient. Flask serves the vanilla-JS `frontend/` directory, `start.py` starts Waitress, and MongoDB stores accounts, signed dataset blobs, evidence, and sessions. `render.yaml` specifies `python start.py`, `requirements.txt`, and `/api/health`.

Hosted account mode requires Render-provided `RENDER`, `PORT`, `RENDER_EXTERNAL_HOSTNAME`, plus secret-managed `MONGODB_URI`, `MONGODB_DATABASE`, a stable 32+ character `AURA_SECRET_KEY`, `AURA_COOKIE_SECURE=true`, `AURA_PUBLIC_DEMO=false`, and `AURA_AUTH_REQUIRED=true`. The Blueprint is configured for this private account mode; it does not enable the shared public-demo workspace.

Waitress binds `0.0.0.0:$PORT`, has one thread/16 connections, a 30-second channel timeout, and 100 MB request body limit. Flask applies 100 MB uploads and parsed-data limits. Render TLS termination, secure HTTP-only SameSite-Strict cookies, trusted-host validation, CSRF checks, and `/api/health` MongoDB ping are implemented.

## Operator steps

1. Create/select a Render Web Service connected to a committed revision (not this dirty worktree).
2. Set build `python -m pip install -r requirements.txt`, start `python start.py`, health `/api/health`, Python 3.12.16.
3. Configure the required secrets and private account mode above. Add custom hostnames to `AURA_TRUSTED_HOSTS` if needed.
4. Optionally mount durable report storage and set `AURA_REPORT_DIR`; otherwise reports are download-only ephemeral files.
5. Deploy manually. Confirm logs contain `Starting AURA-BI on 0.0.0.0:<PORT>`, then test health, login, upload/isolation, Analyst, SIIE, research dashboard/report, blocked/clarification paths, restart, and unauthorized access.
6. Roll back via Render to the preceding known-good committed deployment if health fails. Do not rotate the stable secret unless intentionally invalidating sessions.

Provider costs, MongoDB plan quotas, backups, retention, and actual live behavior are operator/account-specific and unverified here. Deployment does not create independent research evidence.
