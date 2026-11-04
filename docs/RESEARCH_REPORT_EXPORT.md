# Evidence-verified research report export

`POST /api/research/report` accepts the same guarded question request as `/api/research/dashboard`. It recomputes a server-trusted `research-dashboard-contract-v1` from the active dataset; callers cannot supply evidence, chart data, definitions, or provenance as authority.

The endpoint emits a PDF only for `PUBLISH_VERIFIED`. Otherwise it returns HTTP 409 with the pipeline contract, decision, unresolved alternatives, consistency findings, and blocked reasons. It preserves source data and leaves the legacy `/api/report` route unchanged.

For a verified decision, the PDF and adjacent JSON manifest contain report/dataset/version IDs, contract/pipeline version, definitions, source columns, analytical and visualization evidence IDs, verification states, consistency report, publication decision, timestamp, and limitations. The PDF contains only verified analytics and EVVE chart specifications. Conditional, blocked, stale, invalid, or unsupported material is not rendered as a conclusion.

Run `python -m experiments.research_report_measurements` for developer-only timing/RSS smoke data. Do not use it as independent experimental evidence. Evidence binding proves consistency with a computed record, not semantic truth of business definitions.
