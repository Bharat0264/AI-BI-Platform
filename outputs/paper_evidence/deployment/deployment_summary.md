# Deployment evidence status

Status: **PARTIALLY VALIDATED LIVE SERVICE** at `https://aura-bieee.onrender.com`.

On 2026-11-04, certificate-verified HTTPS returned homepage `200`; `/api/health` returned `200` with `{"persistence":"mongodb","status":"ready"}`; and `/api/auth/session` confirmed `auth_required=true` before login. Ten requests each were recorded for the health endpoint, session boundary, and unauthenticated research-dashboard boundary. All protected-dashboard requests returned `401`, confirming that a request without an account cannot access a dataset or run the research pipeline.

These are deployment/engineering measurements only. They do not measure analytical correctness, SIIE/EVVE behavior, dashboard publication decisions, report generation, or independent research performance. The served commit cannot be externally verified because the deployment exposes no version endpoint and no Render service/log access was provided.

Authenticated validation is pending a private test account. No CSRF values, credentials, dataset rows, or private identifiers were retained. Browser automation was unavailable in this environment, so no genuine screenshots were captured.

`figures/endpoint_latency_distribution.png` and `.svg` visualize only the 30 recorded public-endpoint measurements. They are not analytical-performance, baseline, ablation, or independent-evaluation figures.
