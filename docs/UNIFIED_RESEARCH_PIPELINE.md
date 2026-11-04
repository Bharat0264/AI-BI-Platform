# Unified evidence-verified research pipeline

`ResearchDashboardPipeline` is an additive versioned backend contract (`research-dashboard-contract-v1`):

```text
dataset/version → semantic schema + plan → deterministic answer/evidence → EvidenceVerifier
→ SIIE for ambiguity → EVVE chart evidence/specification/verification
→ DashboardConsistencyEngine → publication decision
```

`POST /api/research/dashboard` accepts 1–10 supported question strings and optional expected dataset/workspace guards. It uses the active dataset context and returns the versioned dataset identity, per-question answer, evidence, dashboard components, visualization specifications, consistency report, blocked reasons, and one decision: `PUBLISH_VERIFIED`, `CLARIFICATION_REQUIRED`, or `BLOCKED`.

The endpoint never invokes an LLM, accepts no raw evidence/series from callers, and does not replace `/api/ask`, legacy dashboards, or `/api/report`. The legacy PDF export still only selects current report-eligible evidence and is not labelled evidence-verified visualization output.

Current gaps before production/report integration: dashboard consistency is invoked by the new opt-in endpoint only; the legacy Plotly UI and PDF visualizations do not consume EVVE contracts. An opt-in research report can serialize this endpoint’s returned contract, but it must include only `PUBLISH_VERIFIED` components and attach blocked/conditional content as exclusions, never findings.
