# Release candidate runbook

## Current status

The implementation for Phases 1–12, plus account security and isolated storage, is prepared for source delivery. The fresh Python 3.12 environment passes regression tests and a dependency audit. Earlier phase reports are historical; see ACCOUNT_SECURITY.md for the final account model. No public service has been deployed or real database migrated in this work. Public deployment remains gated pending staging/infrastructure validation.

## Local setup

1. Use Python 3.12.16 (.python-version) and create a new virtual environment: `py -3.12 -m venv .venv`. Do not reuse the old Python 3.10 virtual environment.
2. Install `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints-local-win-py312.txt`. This snapshot pins the tested package versions, but is not a hash-locked production image. Windows/Edge was tested locally; GitHub Actions provides the separate Linux/Chromium check after push.
3. Copy .env.example only if .env does not exist. Configure a separate evaluation MONGODB_URI and MONGODB_DATABASE, AURA_AUTH_REQUIRED=true, a private random AURA_SECRET_KEY of at least 32 characters, and AURA_COOKIE_SECURE=false for local HTTP only. Set secure cookies true for HTTPS. Read ACCOUNT_SECURITY.md before provisioning.
4. Run `python scripts/manage_user.py --username analyst@example.com`. It prompts privately for the password, creates that account's namespace/indexes and revokes prior sessions on password reset. MongoDB credentials must have permissions for the authentication and provisioned account databases. Use a separate evaluation database, not production credentials.
5. Run `python start.py` and open http://127.0.0.1:10000. Sign in, upload a dataset, inspect/confirm its column meanings, then ask an exact-column total and review evidence. Try a date comparison and saved-definition recalculation.
6. Sign out to revoke the session; stop the process with Ctrl+C.

Real account provisioning writes MongoDB. No such command was executed against real infrastructure during verification; tests use disposable mocked databases. The application requires MongoDB and will fail startup without valid connectivity. There are no seeded/default production accounts or working default secret.

## Source package

The source-only archive excludes data CSVs, active datasets, virtual environments, .env credentials, generated reports and Git history. It contains a per-file SOURCE_MANIFEST.json and has an accompanying .sha256 file. These detect content changes; they are not signed publisher authenticity. Rebuilding unchanged source on this toolchain yields the same ZIP bytes. The demo button returns an unavailable response until its data file is supplied separately; upload your own data instead. Original checkout data is retained.

The old constraints-local-win-py310.txt is retained as a historical Phase 12 artifact; it cannot install the patched account release. Use the Python 3.12 file.

## Runtime and storage boundaries

start.py validates loopback binding before importing the app, uses one Waitress application thread, 16 connections, a 30-second idle-channel timeout, 100 MiB body limit and untrusted proxy-header clearing. The direct development server also validates local-only options. These settings do not provide CPU deadlines or process-memory caps.

Authenticated requests resolve separate account database namespaces and request-scoped active data. They never use shared local dataset caches. Snapshot HMACs bind the blob to the account and signing secret before deserialization. Legacy AURA_AUTH_REQUIRED=false still uses the old shared dataset architecture and must be confined to isolated loopback evaluation. Old immutable blobs are retained for in-flight readers; define a storage retention/quota policy before hosting. Reset removes the active pointer, not a cryptographic erasure of every retained blob.

Rotating AURA_SECRET_KEY invalidates sessions and existing snapshot signatures; plan source re-import. Database administrators must remain trusted. Do not load untrusted pickle/cache backups or run optional SQLite migrations from an untrusted source. Authenticated users cannot use the server filesystem SQLite connector.

## Validation

```powershell
python -m pytest tests -q --junitxml=test-results.xml
node --check frontend/auth.js
node --check frontend/app.js
node --check frontend/analyst.js
python -m experiments.accuracy --suite scope --output outputs/final-scope
python -m pip check
python -m pip_audit --progress-spinner off --format json --output dependency-audit.json
python scripts/package_release.py --output aura-bi-local-rc.zip
```

The dependency audit must not suppress findings. Regression and audit GitHub Actions workflows use verified immutable action commits, read-only repository permissions and no production secrets. Local results do not certify a remote CI result. No raw uploaded data is included in CI artifacts.

The fresh Python 3.12 environment installs dnspython 2.9.1, Pillow 13.0.0 and filelock 4.2.6, resolving the advisory entries from the old Python 3.10 environment. A zero-known-findings scan is evidence about that environment at that time, not a security guarantee.

## Public deployment gates

`python scripts/release_check.py --target public` intentionally exits 2 with known unresolved deployment requirements. `--target local` reports LOCAL_EVALUATION_ONLY without claiming that credentials/startup were validated. The Render blueprint disables auto-deploys and runs the failing public gate; it is intentionally not deployable yet. Editing/pushing source is not a live service configuration change, although your own connected hosting integrations can react to repository events.

Before restoring a hosted start command, verify: real MongoDB account permissions and TLS; server secret/cookie/hostname/proxy policy; a patched deployment image and its audit; hard memory/CPU/request execution limits; edge rate limits; representative concurrent HTTP/database load; account isolation on staging; account/dataset quotas and blob retention; a real database/GridFS/file backup and restore rehearsal. Authentication, private account isolation, application request limits and local adversarial tests are implemented, but do not substitute for those operational checks. Public network binding remains rejected by start.py until the release configuration is reviewed and changed intentionally.

Shared-team RBAC, SSO/MFA, email password recovery and collaborative workspaces are not part of the implemented private-account model. Profile role labels confer no cross-account administrator privileges.

## Rollback

No live deployment or migration has occurred, so there is no production rollback to perform. Keep the prior source archive and checksum. Before any future real deployment, back up MongoDB including authentication data, account databases and GridFS, plus local generated files and private configuration; verify restoration into a separate environment. Source archives are not data backups. Rehearsal against real infrastructure remains an operator task.

## References

Pylons Project, Waitress 3.0.2 arguments: https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html

Render, Blueprint YAML Reference: https://render.com/docs/blueprint-spec

Pallets, Flask security and session API: https://flask.palletsprojects.com/en/stable/web-security/ and https://flask.palletsprojects.com/en/stable/api/#sessions

Documentation accessed 2 November 2026.
