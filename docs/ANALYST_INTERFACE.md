# Phase 5: AI Analyst interface

Implemented locally in the existing Flask/vanilla-JavaScript app. No commit, push or deployment performed.

## What users can do now
1. Open AI Analyst and ask a supported question such as `What is sales?`.
2. If multiple measure columns are detected, compare their computed results in separate cards. Choose `Use for this question` to make a one-time selection. This does not save a default.
3. Select `Remember as sales…` or use the Business definitions form. Review the exact workspace, dataset, chosen column and version being replaced, then explicitly confirm. Cancel makes no change.
4. Manage terms sales, revenue, profit, cost, costs and quantity. Review disabling a default without deleting history. View version history, including actor labels and confirmation times.
5. See the chosen measure, calculation, saved version and freshness beside the answer. Expand View Evidence for the plan, definition, numerical verification and evidence.
6. Inspect answer history with Current, Needs updating, Needs clarification or Tracking incomplete indicators and plain-language reasons. View an original answer without recalculating it.
7. Select Preview recalculation to compare the original and new answers side by side. Save as new answer only after review; the old answer remains available. Unresolved previews cannot be saved.
8. Generate a PDF from Export Center, or regenerate a tracked report from its history card. Downloads create separate files. Historical filters are retained for regeneration.

Analyst questions explicitly use all supplied rows; dashboard filters do not apply to them. Report exports retain their separate dashboard-filter behavior.

## Scope and error handling
- Confirmation requests include the workspace and dataset IDs that the user reviewed. The API rejects a save if either changed before confirmation, even when the new workspace has no previous versions.
- Version collisions require another review. A stale recalculation fingerprint discards the old preview and requires a new one.
- Pending UI state is cleared when an uploaded dataset changes. Older async callbacks cannot replace the new context's answer. Loading a mixed snapshot across refresh requests requires a fresh status read.
- Duplicate actions are blocked while a request is running. Failed asks clear obsolete interpretation choices, report the error and release controls.
- Freshness refreshes when entering AI Analyst, after relevant actions, or through Refresh status. Current is a dependency-freshness label, not certification of analytic correctness.
- Exact-column questions and one-time selections retain their precedence over saved defaults. Changing an unrelated default does not change an explicit selection.
- Business choices remain limited to detected existing measure columns. No inferred returns/tax formula, currency conversion, time comparison or unrestricted natural-language query support is added.

## Implementation
- frontend/analyst.js: isolated controller for the analyst workflow, explicit confirmations, history, replay previews, report downloads and race/error handling.
- frontend/index.html, styles.css, app.js: existing screens extended with labelled controls, live status messages, responsive panels and the controller integration.
- Backend definition responses now expose the detected column roles and display context. They accept optional expected_workspace_id/expected_dataset_id guards on writes. History responses identify their scope.
- Resolved definitions and clarification responses expose the parsed business term; UI code does not guess which term to save from prose.
- Saved answer records retain their plan; detail reads return their workspace/dataset-scoped evidence for review.

## Validation actually performed
- Full suite: 108 passed in 21.36 seconds. This includes all earlier backend tests and 7 new real-browser regression tests.
- Browser: Microsoft Edge, driven headlessly through Playwright, with the real HTML/CSS/JavaScript and Flask analyst/definition/replay/report endpoints.
- Tested: use-once versus remembered choices, confirmation cancellation, version update and disable, old/new comparison and immutable history, version conflicts, switching workspace before saving, narrow layout, escaped user input, report download/regeneration, changed replay previews, failed asks and control recovery.
- Desktop viewport 1440 x 1050 and mobile viewport 390 x 844. Mobile document width was checked against viewport width; screenshots were inspected for readability and layout.
- node --check passed for analyst.js and app.js. git diff --check passed.
- Tests use synthetic data, mongomock and a temporary Flask server. Plotly rendering is stubbed; PDF route tests use placeholder PDF bytes. These tests do not validate real model calls, production MongoDB, PDF layout, forecasting/chart quality, real financial data, large histories or full accessibility compliance.

## Reproduce
Install requirements-dev.txt. Run `.venv/Scripts/python.exe -m pytest tests -q` on Windows. Browser checks use installed Edge by default on Windows; elsewhere install Playwright Chromium with `python -m playwright install chromium`. Set AURA_UI_BROWSER_CHANNEL to choose another installed supported browser channel. If no browser is installed, browser tests skip with an explanation.

Set AURA_UI_CAPTURE_DIR to an output directory to capture the conditional-choice, recalculation and mobile screenshots while running the browser tests. The screenshots provided with this summary show a synthetic demonstration, not business or benchmark results.

## Remaining work
The interface now exposes Phases 1-4. Evaluate it with real user tasks and independent numeric ground truth next. The current question grammar remains bounded, histories show at most the latest 100 items, and production concurrency, load, accessibility and cross-browser coverage need separate validation. None of these test results establish that the product is globally unique or best in its category.
