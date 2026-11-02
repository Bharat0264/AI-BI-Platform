# Phase 10 — Security and performance

Implemented locally on 2 November 2026. Local hardening and measurement are complete; **public-release security is not cleared**. No commit, push or deployment.

## Confirmed changes

- Cross-site browser API requests are rejected using Origin and Sec-Fetch-Site checks. Checks cover GET routes too, because report/analysis GET handlers can create artifacts. Same-origin browser requests and originless non-browser clients remain supported. This is a browser boundary, not authentication or a complete CSRF token system.
- Responses disable MIME guessing and framing, restrict referrers to the same origin, and prevent API response caching. No restrictive CSP was enabled without auditing the existing third-party chart resources.
- Multipart limits: 20 parts, 64 KiB per non-file field; existing total request limit remains 100 MiB.
- Parsed imports: at most 1,000,000 rows, 200 columns, and 512 MiB estimated DataFrame memory; nonempty data and unique columns required. CSV reads stop after the row limit plus one sentinel row. Excel reads use the same sentinel count.
- XLSX ZIP metadata is checked before XML parsing: at most 2,000 entries, 256 MiB advertised expanded size, no encrypted members. This check does not provide a hard process-memory guarantee; JSON and column/memory checks occur after parsing, legacy XLS lacks the ZIP preflight. Worker/container limits remain necessary.
- Malformed JSON objects and empty/invalid CSV uploads return controlled 400 responses. Questions are limited to 2,000 characters.
- SQLite imports remain confined to the project path and validated table identifiers. Connections now use URI mode=ro and PRAGMA query_only. Missing files are not created. Connection errors do not expose source paths or SQL details to clients.
- Direct development-server startup now binds to 127.0.0.1 by default. HOST can override it deliberately. Existing production WSGI commands require their own network controls.
- Date-scope validation checks distinct date values instead of repeatedly validating identical strings. Every source row still participates in the date filter and evidence selection. No global cache or stale-data risk was added.

## Confirmed validation

- Full suite after dependency changes: **360 passed in 41.55 seconds**, including the existing browser suite. No skips reported.
- Independent scope arithmetic evaluation: **70/70 passed**, zero incorrect resolved answers or unexpected exceptions.
- New tests cover cross-origin rejection, same-origin acceptance, malformed JSON shapes, response headers, ZIP member limits, invalid workbook input, dataset shape limits, bounded CSV reads, invalid uploads, question length, missing SQLite files and invalid repeated date values.
- pip check: no broken requirements.
- A limited pattern scan of application directories, README and .env.example found no matching common API/private-key patterns. This was not a full history or entropy-based secret audit.

## Reproducible performance measurement

Full-row date-scope compilation on the historical retail file: **541,909 rows**, 23,260 distinct timestamps. Three alternating-order repetitions per implementation. Median before **8.726s**, after **0.610s**, ratio **14.3x**. All six runs selected the same 35,147 rows and identical row-position SHA-256. Python allocation peak after: 37,216,065 bytes.

This measures scope compilation only, not total dashboard/API latency or production throughput. It uses a task-column projection across every row. Python tracemalloc is not process RSS. Timings depend on this Windows machine and load; no statistical confidence or concurrency capacity claim is made. The benchmark reconstructs the prior validation loop in memory, differing only in distinct-value validation.

## Dependency audit and unresolved release blockers

The installed-environment pip-audit scan initially reported 82 advisory entries across six packages. Updated local development/build tools: pip 26.2.2, setuptools 84.2.1, pytest 9.0.3. Updated requirements-dev.txt to the tested pytest and pip-audit versions. Pytest 9.2.0 was tried but raised an internal NodeId error on this environment; the patched 9.0.3 version passes all tests.

The final scan reports **57 advisory entries across three packages**. Entries are scanner reports, not 57 independently confirmed exploitable application flaws. No findings were suppressed. Attempting all listed fixes failed because those releases were not available from the configured package index; pip index versions confirmed the installed versions were the newest available there at the time. No unverifiable version was added to requirements.

| Package | Installed | Advisory entries | Listed fix |
|---|---|---:|---|
| dnspython | 2.8.0 | 1 | 2.9.0 |
| filelock | 4.1.0 | 17 | 4.2.1 |
| pillow | 12.3.0 | 39 | 13.0.0 |

**Uncertain:** advisory exploitability in this app and availability from other authorized indexes. Review the raw IDs/descriptions and upstream release status before release. Re-audit in the actual deployment image; this report describes the local environment, including development tools.

**Known architecture blockers:** the application has no enforced authentication/authorization and uses process-global active data and shared workspace settings. Origin checks cannot stop direct clients and are not user isolation. Do not publish sensitive data or run public multi-user access until identity and per-user storage are implemented. Multiple workers can disagree about the active dataset. Server-controlled cached/GridFS pickle data is still deserialized; only trusted administrators may modify those stores. Pandas explicitly warns against loading untrusted pickles. Uploaded files are not accepted as pickle inputs.

Additional work before public deployment: hard worker/container memory and timeout limits, rate limits, authenticated authorization tests, trusted-host/proxy configuration, HTTPS, storage permissions, dependency fixes, representative concurrent API/database load tests and an end-to-end HTML/CSP review. No production load test or penetration test was performed. These remain recorded release gates, not claimed completed checks.

## Reproduction

From the repository root, with the development dependencies installed:

```powershell
python -m pytest tests -q
python -m experiments.accuracy --suite scope --output outputs/phase-10-scope
python experiments/security_performance.py --source data/data.csv --output outputs/phase-10-performance.json
python -m pip_audit --format json --output outputs/phase-10-dependency-audit.json --progress-spinner off
python -m pip check
```

pip-audit returns exit 1 when advisory entries remain; preserve and review its report. Tooling installation also updates the local environment; requirements-dev.txt records the tested test/audit tool versions. Runtime dependency locking and full deployment-image scanning remain release work.

## Primary references

- Flask / Pallets, *Security Considerations*, version 3.1 documentation, accessed 2 November 2026: https://flask.palletsprojects.com/en/stable/web-security/ — request resource limits, CSRF and response headers.
- pandas development team, *pandas.read_pickle*, documentation accessed 2 November 2026: https://pandas.pydata.org/docs/reference/api/pandas.read_pickle.html — untrusted deserialization warning.
- Python Packaging Advisory Database, machine-readable findings retrieved by pip-audit 2.10.1; original and final JSON reports accompany this document. Applicability requires separate review.

## Next

Phase 11: usability and polish. Phase 12: release preparation, with the security gates above required before any public deployment. A world-leading or production-secure ranking has not been established.
