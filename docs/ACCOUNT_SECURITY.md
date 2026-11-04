# Account security and isolated storage

Implemented during final phase completion on 2 November 2026. This document supersedes the missing-authentication and shared-data descriptions in the historical Phase 10–12 reports. Render hosting is supported with mandatory account security; real infrastructure validation remains necessary. See RENDER_DEPLOYMENT.md.

## Current deployment mode

The current Render Blueprint requires private accounts: `AURA_PUBLIC_DEMO=false` and `AURA_AUTH_REQUIRED=true`. A historical shared public-demo mode remains implemented for isolated demonstrations only, but must not be enabled for controlled research or private data. Retain the signing key because it binds account snapshot integrity and sessions.

## Operator setup

Use Python 3.12.16 as recorded in .python-version. Install requirements-dev.txt, or requirements.txt without test/audit tools for runtime-only installation. The old Python 3.10 constraints file is historical and cannot install the security-patched dependencies.

Copy .env.example only if .env does not already exist. Set MONGODB_URI and a MONGODB_DATABASE base of 1–24 letters, digits or underscores. Use a separate evaluation cluster/database and appropriate least-privilege MongoDB credentials. Account storage requires access to the base_auth database and generated account/demo databases (names fit Atlas’s 38-byte limit). Grant only the actual required databases; this application does not configure MongoDB server roles.

Set AURA_AUTH_REQUIRED=true and AURA_SECRET_KEY to a unique random secret of at least 32 characters. Generate it privately using Python's secrets.token_hex(32), then store it in your secret manager or .env. Do not publish it, reuse the test fixture key or send it in chat. AURA_COOKIE_SECURE=false is required for local HTTP testing; HTTPS deployments must use true.

Provision an account from the repository root:

```powershell
python scripts/manage_user.py --username analyst@example.com
python start.py
```

The command securely prompts for and repeats a password of 12–1,024 characters. It initializes that account's indexes and defaults, writes a Werkzeug scrypt hash, and revokes prior sessions when resetting an existing password. It does not accept passwords in command-line arguments. To disable an account and revoke sessions, run `python scripts/manage_user.py --username analyst@example.com --disable`.

No actual user credentials or real MongoDB accounts were provisioned during automated verification. Tests use disposable mocked databases and clearly marked test passwords.

## Implemented boundaries

- All existing data/settings/analysis API routes require a valid, unexpired account session when account mode is enabled. Session, login and health endpoints are the documented exceptions. Provisioning has no public registration or administrator endpoint.
- Signed HTTP-only SameSite=Strict cookies carry a random session reference and request token. The server stores only a hash of the session reference. Sessions expire after eight hours, are revoked on logout/password reset, and are rejected immediately for disabled accounts. Passwords never enter browser persistent storage.
- Mutating requests, including sign-in/sign-out, require a session-bound X-CSRF-Token. Successful login rotates both the session reference and token. The existing Origin/Sec-Fetch-Site browser checks remain in place.
- Login has shared database attempt limits: 30/IP and 10/username per 15-minute bucket. Account API traffic has 120 general requests/minute and 10 expensive-analysis/report/market requests/minute per account. These are fixed-window limits, not a replacement for edge rate limiting or execution deadlines.
- A ContextVar carries the authenticated account through each request and resets during teardown. Every repository, legacy setting/record and GridFS operation resolves a database namespace derived from the immutable account ID. A workspace name, user_id request field or guessed artifact ID cannot select another account's database.
- Authenticated active data is loaded from that namespace into the request only. No authenticated request reads or writes the legacy shared local pickle/cache. A new process can read the same persisted snapshot; mutable process-global active data is used only in explicitly disabled-auth legacy mode.
- Snapshot blobs are HMAC-verified with the secret and account ID before pickle deserialization. Invalid, unsigned or cross-account signatures produce a conflict requiring re-import. Secret rotation intentionally invalidates existing cookies and snapshot signatures; plan re-import before rotating. Metadata pointers change atomically; old immutable blobs are retained to avoid breaking in-flight readers. Storage quotas and lifecycle retention remain an operator responsibility.
- The server-side SQLite file connector is disabled for authenticated accounts to prevent server filesystem access. Users upload their own data instead.
- Switching accounts reloads the page, clearing the previous account's UI state. “Admin/Analyst/Executive” profile labels are display labels within a private account, not shared-team authorization grants. Shared-team roles, password recovery/email, SSO, MFA and cross-account collaboration are not implemented or claimed.

## Verification

Backend tests walk the entire API route map for unauthenticated rejection; check bad credentials, missing request tokens, sign-out/captured-cookie revocation, password reset/disabled users, login limits, account-specific answers/records/reset, guessed artifact IDs, spoofed workspace/user fields, tampered snapshot rejection before deserialization, and simultaneous requests for two accounts. A real browser check signs in, uploads, asks a question, signs out and signs in as another account without retaining its dataset.

MongoDB/GridFS transport is mocked in these tests. No live Atlas permissions, durability, operational backups, production throughput or penetration-test claim follows from these checks. start.py remains loopback by default locally; on Render it binds the platform port only after validating account security, secure cookies and trusted host configuration. Legacy unauthenticated mode cannot run on Render.

## Dependencies and CI

A fresh Windows Python 3.12.16 environment resolved dnspython 2.9.1, Pillow 13.0.0 and filelock 4.2.6, removing the 57 advisory entries observed on the old Python 3.10 environment. Runtime/development minimums prevent silently selecting those older vulnerable releases. The final machine-readable audit and test results document the current finding count; an empty audit is not proof of absence of vulnerabilities.

GitHub Actions runs regression/browser tests on Python 3.12 and separately audits dependencies without suppressing findings. Action refs are pinned to verified commit hashes. CI runs on GitHub only after push; local checks do not establish a remote CI result.

## Primary references

Flask/Pallets, Security Considerations and Sessions API, documentation accessed 2 November 2026: https://flask.palletsprojects.com/en/stable/web-security/ and https://flask.palletsprojects.com/en/stable/api/#sessions

Werkzeug/Pallets, Security Helpers, documentation accessed 2 November 2026: https://werkzeug.palletsprojects.com/en/stable/utils/#werkzeug.security.generate_password_hash

Database naming compatibility: already-valid base_u_<hash> names of at most 38 bytes are retained. Longer names now use a three-character readable prefix, _t_, and a 128-bit digest of the full base name plus account identity. This keeps names within 38 bytes without mixing bases sharing a prefix. Oversized databases on a different, less-restrictive deployment are not renamed or deleted automatically; an operator must plan migration if such databases already contain data.
