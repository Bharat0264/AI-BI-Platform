# Phase 11 — Usability and polish

Implemented and verified locally on 2 November 2026. No commit, push or deployment.

## Delivered

- The AI Analyst now shows a plain-language summary of the scope for the **next question**. Changing region/category selections or date periods updates it immediately. Clearing the controls restores “all uploaded rows.” The existing answer keeps its original scope, which remains in its evidence and answer text.
- Empty questions, incomplete periods, reversed date ranges and overlapping comparison periods show an error beside the question. The first field needing correction receives focus and aria-invalid. Invalid inputs do not send an analytical request. Editing or clearing controls removes the validation state.
- Ctrl+Enter or Command+Enter submits a question; ordinary Enter remains available for new lines. Questions have the same 2,000-character bound as the API.
- The request button shows “Working…” while actions are running, and the analyst section exposes aria-busy. Existing busy controls prevent duplicate submissions. Failed question requests restore the controls and allow retrying.
- Answer outcomes distinguish calculated results, column-meaning choices and insufficient-data results. Unsupported questions show a practical next step instead of reporting “Answer ready.” Freshness badges still describe dependency state separately from numerical verification.
- Upload controls now say “Import dataset” and name CSV, Excel and JSON. A visible 100 MB limit matches the existing request policy. Unsupported extensions and oversized files are rejected in the browser before import; server validation remains authoritative.
- Failed replacement imports preserve the answer and definition context already on screen. A successful import/demo replacement resets that context before rendering the new dataset.
- Added visible keyboard-focus outlines, wrapping for long answer/evidence text, and reduced-motion CSS. Mobile layout checks wait for the browser to complete responsive layout after viewport changes, then verify there is no horizontal overflow.

## Verification

**369 tests passed in 42.90 seconds**, including **21 real-browser checks** using headless Microsoft Edge and a local Flask server. JavaScript syntax checks and git diff whitespace checks passed.

Nine new browser cases cover:

1. Empty-question focus, cleared errors and keyboard submission.
2. Reversed current dates, with no query sent.
3. Overlapping comparison dates, with no query sent.
4. Reversed comparison dates, with no query sent.
5. Next-question scope summary, preserved earlier answer and narrow-screen layout.
6. Busy state, failed-request recovery and successful retry.
7. Helpful insufficient-data outcome.
8. Rejected file type preserving the current answer.
9. Failed replacement upload preserving the current answer.

Existing browser coverage continues to check selected interpretations, saved definitions, conflicts, reviewed recalculation, escaping, explicit scopes, general-data uploads and report downloads. Screenshots phase-11-desktop.png and phase-11-mobile.png were generated from a small synthetic fixture and visually inspected. They illustrate the UI, not new real-business findings.

## Scope and limits

The existing Flask/vanilla-JavaScript interface and analytical calculations are retained. No source data is rewritten by these UI changes. This is a focused usability pass, not a complete product redesign or accessibility certification. No user study, screen-reader audit, Safari/Firefox compatibility study or browser automation of actual speech recognition was performed. The fixture mocks database infrastructure, narration and chart/PDF rendering; it exercises real local routes and DOM interactions.

The scope summary labels dates as configured; the API still validates actual date values, semantic roles and data completeness. A summary is not proof that a query is supported. Failed uploads preserve local context when the server rejects the replacement; ambiguous network failures after a server-side write still require refreshing the active dataset.

**Phase 10 release gates remain open:** enforced authentication/authorization, per-user data isolation, dependency-advisory resolution, deployment resource limits and representative concurrent load testing. This phase does not clear public deployment or establish a world-leading ranking.

## Reproduce

From the repository root:

```powershell
node --check frontend/app.js
node --check frontend/analyst.js
python -m pytest tests -q
```

To reproduce screenshots, set AURA_UI_CAPTURE_DIR to a desired output directory, then run `python -m pytest tests/test_analyst_ui.py -q`. Browser tests require the development dependencies and Edge, or a configured Playwright browser.

## Next

Phase 12 is release preparation. Review and resolve the recorded release gates before any public deployment. Nothing has been pushed or deployed.
