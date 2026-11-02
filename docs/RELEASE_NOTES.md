# Release notes — phases 1–12 and account completion

Prepared 2 November 2026. This source release includes the planned analytics phases plus administrator-provisioned private accounts. Public hosting is still gated pending real staging and operational validation.

## Delivered

- Explicit/conditional measure selection, saved business definitions and scoped versioning.
- Immutable answer history, dependency freshness and reviewed recalculation.
- Whole-question parsing, guarded unsupported-question refusal and independent numerical checks.
- Explicit row filters, source date formats and calendar-period comparisons.
- Historical public-data validation with unresolved opaque-column meanings reported honestly.
- Bounded imports, browser-origin boundaries, read-only local SQLite connector and faster repeated-date validation.
- Scope previews, focused errors, keyboard submission and mobile layout checks.
- Administrator-provisioned accounts with password hashing, request-token checks, expiring/revocable server sessions and login/API limits.
- Account-specific database namespaces and request-scoped active datasets. No authenticated account uses the shared legacy local cache. Signed snapshots are checked before deserialization.
- Fresh Python 3.12.16 dependencies, reproducible environment constraints, local-only launcher, deterministic source packaging, operational runbook and pinned regression/security GitHub Actions workflows.

## Current evidence

See docs/validation/summary.json and the accompanying raw reports for the measured final test/audit/evaluation results. These supersede earlier phase reports, which remain historical records. Tests use mocked MongoDB transport and real local HTTP/browser interactions where stated; they do not certify a live deployment.

## Behavior changes

The account release requires Python 3.12.16 and a new virtual environment; the old Python 3.10 dependency snapshot is historical. AURA_AUTH_REQUIRED=true requires a private random signing key and explicitly provisioned MongoDB accounts. There is no default production password or self-registration. See ACCOUNT_SECURITY.md.

start.py defaults to loopback port 10000 and rejects public binding. render.yaml keeps auto-deploy disabled and intentionally fails its public gate. These are source changes; no hosted environment is configured by this work. Uploaded/demo CSVs, credentials, caches and generated reports are omitted from source packages. Financial views require supplied financial measures and a usable date; other datasets use the analyst and inspection flow.

## Remaining external validation and product boundaries

Public infrastructure must verify MongoDB permissions/TLS, secure cookies/secret management, resource limits, edge rate limits, host/proxy configuration, storage quotas/retention, load and backup/restore. Do not remove the deployment gate merely to obtain a passing startup check. Shared-team RBAC, SSO/MFA, recovery email and collaborative workspaces are outside the delivered private-account model.

Opaque cnt/campaign fields still require explicit semantic confirmation; the platform does not guess dataset-specific meanings. Benchmark cases are developer-designed, and no real-user study, penetration test, competitive ranking or novelty guarantee has been established.
