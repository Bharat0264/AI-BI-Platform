# Research report validation

Environment: CPython 3.12.16, pytest 9.0.3, Playwright Chromium installed. Final regression was executed as two non-overlapping test-file batches because the execution environment limits individual command duration: 177 passed in 29.92 s and 285 passed in 4.05 s. The two report-export tests passed separately. Total: **464 passed, 0 failed**.

Developer-only engineering smoke measurement (`experiments.research_report_measurements`) on an in-memory three-row fixture recorded: pipeline 0.007927083 s, manifest 0.000006333 s, PDF/JSON generation 0.002369125 s, and maximum RSS 169,902,080 bytes. These are one-machine smoke measurements, not independent evaluation, performance comparisons, or publication results.

The report gate rejects unsupported/ambiguous output with HTTP 409, and report-manifest construction raises for any non-`PUBLISH_VERIFIED` contract. Tests cover a verified contract/manifest/PDF, ambiguity, bad request, dataset guard, invalid chart/scope/currency/staleness through the underlying pipeline and consistency suites, lifecycle behavior, security, and browser/auth routes.

Remaining limitations: the endpoint recomputes trusted evidence but does not register a research report in the legacy report collection; legacy PDF/Plotly output remains unverified. The endpoint must not be used as evidence of business-semantic truth or independent research effectiveness.
