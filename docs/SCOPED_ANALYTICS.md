# Phase 8: Explicit filters and calendar-period comparisons

Implemented locally on 2 November 2026. No commit, push or deployment performed.

## Result

The AI Analyst now has an optional “Filter rows or compare date periods” panel. Users can select region/category labels, choose a date column, specify an inclusive current interval and optionally compare a non-overlapping baseline. The source upload remains unchanged.

- Full regression suite: **327 passed in 35.59 seconds**, including 10 real-browser tests.
- New independent scope evaluation: **70/70 passed**; 62 resolved outputs matched the independent reference, 0 unsafe unconditional answers and 0 unexpected exceptions.
- Original arithmetic/guard evaluation: **332/332 passed**.
- Language/qualifier evaluation: **154/154 passed**.
- Legacy benchmark smoke, JavaScript syntax checking and git diff --check completed successfully.

These are developer-authored synthetic checks. They are not a real-user trial, a blinded benchmark or proof of world-leading/general accuracy.

## User flow

1. Open AI Analyst and expand the scope panel.
2. Choose the actual Region/Category columns and one or more exact labels. Leave filter values empty to include all labels.
3. For dates, select an explicit date column and enter both current-period bounds.
4. Optionally enter both baseline bounds. The periods must not overlap.
5. Ask a supported ordinary question such as `What is revenue?` or `What is average profit?`.
6. Review the scope and result in the answer and View Evidence. Clearing controls changes the next question, not a previously asked question's scope.
7. If the measure is ambiguous, select an interpretation. Only current-period alternatives are displayed initially; the baseline comparison waits for an explicit measure choice. Choosing an interpretation reuses the original question's scope even if the controls were subsequently cleared.
8. Recalculation previews and saved answer history retain the original scope and dataset snapshot. New definitions can change the selected measure on replay, but cannot erase the recorded row/date filters.

Dashboard filters and report metric filters remain separate from analyst scope. A PDF evidence entry retains its own scope; generating a report does not automatically copy the analyst's date controls into dashboard calculations.

## API request

POST /api/ask accepts a scope object alongside the question:

```json
{
  "question": "What is revenue?",
  "scope": {
    "filters": {"Region": ["North"], "Category": ["Office"]},
    "date_column": "Order Date",
    "period": {"start": "2025-02-01", "end": "2025-02-28"},
    "compare_to": {"start": "2025-01-01", "end": "2025-01-31"}
  }
}
```

Use the real column names. Filter lists use OR within a column and AND between columns. Matching is exact and case-sensitive. Unknown labels or columns, empty API filter lists, unsupported roles and colliding text labels are rejected. At most two filter columns and 200 requested labels per column are accepted. The browser lists the first 200 distinct options per supported column and discloses truncation; the API can select another known label explicitly.

An omitted/null/empty scope object uses the ordinary unfiltered path. A nonempty scope containing no effective filter or period is rejected. Date periods require an explicitly selected column with a date/time semantic role. No automatic choice between order date, ship date or another date field is made.

The browser includes the workspace and dataset IDs it reviewed. If those changed before the request, the API returns 409 rather than executing an obsolete UI selection in another scope.

## Date semantics

- Request bounds are strict YYYY-MM-DD calendar dates, start <= end.
- Both entered dates are inclusive. Execution uses [start, day-after-end), and evidence records both inclusive and exclusive boundaries.
- Source values must be date objects, naive datetimes, ISO date strings or naive ISO timestamps with minute/second precision and optional fractional seconds. Ambiguous numeric formats, invalid/missing dates and timezone-aware values require correction before date-scoped execution.
- Dates are interpreted in their supplied naive source calendar. No timezone conversion or relative-date resolution is performed.
- Date validation applies after explicit category/region predicates. An invalid date on a row explicitly excluded by those predicates does not contaminate the selected scope. An invalid date whose period membership is unknown is not silently dropped.
- Empty periods return INSUFFICIENT DATA. An absence of rows is not asserted to be a measured zero because source completeness is unknown.
- Unequal period lengths are allowed, disclosed and not normalized. Gaps between observed transactions do not establish incomplete or complete business coverage.

For schema profiling only, mixed-timezone parseability is reduced to a parseable/not-parseable signal without warning-driven dtype failures. This does not convert dates used in scope execution; timezone-aware execution still rejects.

## Comparison arithmetic and verification

Single-period scopes support existing totals, row means, grouped breakdowns and highest/lowest group questions. Two-period comparison currently supports one ungrouped total or row mean.

- Current value and baseline value are calculated separately under identical categorical filters.
- Difference = current - baseline.
- Percentage = (current - baseline) / baseline * 100, only for a strictly positive baseline.
- A zero baseline reports an undefined percentage; a negative baseline reports no percentage rather than implying a growth rate. A non-finite derived percentage is omitted explicitly. Non-finite differences are rejected.
- Changing currency between periods requires an explicit conversion policy and is rejected. This phase adds no currency conversion.
- Matching rows, valid numeric rows used and invalid numeric exclusions are recorded and disclosed. Means are means of valid rows, not daily means, entity means or weighted means.
- The answer discloses each period's calendar length, no normalization and unknown source completeness. It makes no causal claim.

A comparison stores three immutable evidence records: current calculation, baseline calculation and their derived comparison. Claims bind to exact current, baseline, difference and optional percent-change result paths with the corresponding predicates. Comparisons are not accepted when either source result has not passed verification.

## Row evidence and lifecycle

Scope compilation records canonical predicates, original source row count, selected row count and a SHA-256 fingerprint of selected zero-based source row positions. Row position identity does not depend on DataFrame index labels. This is compact reproducibility metadata; the full raw rows are not sent to a model.

Business roles are inferred/confirmed on the original source and frozen during scoped calculations. Filtering cannot silently reclassify a column because its distribution changed.

Filter/date columns are added to evidence source columns, so relevant semantic corrections invalidate dependent artifacts. The saved replay request includes scope. Comparison evidence references both source evidence IDs; lifecycle checks traverse these dependencies. Missing or stale components cannot remain labelled Current. Source records and prior answers remain unchanged.

## Independent evaluation

The new 70-case scope matrix contains 60 seeded arithmetic cases, two nonpositive-baseline edge cases and eight invalid-scope cases. It uses Python date selection, Decimal arithmetic and struct-packed row-position hashes independently of the pandas execution path. Checks include amounts, means, differences, percentages, predicate bounds, required scope columns and selected-row fingerprints.

Regression tests deliberately corrupt a row fingerprint, date boundary and comparison difference while leaving status/verification unchanged. The independent evaluator detects the corruption.

Additional tests cover date endpoints, duplicate DataFrame indices, filtered-out invalid dates, source semantic corrections, multiple date columns, cross-currency periods, invalid scope structures, no-row windows, overlap, ambiguous measures, saved defaults, immutable replay and missing dependency evidence.

The two new browser tests cover selecting a full scope and preserving it through interpretation choice, and blocking a question with incomplete date controls before sending an unfiltered request. Desktop/mobile layout was checked; the provided controls screenshot was inspected.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe experiments/accuracy.py --suite scope
.\.venv\Scripts\python.exe experiments/accuracy.py
.\.venv\Scripts\python.exe experiments/accuracy.py --suite language
```

The script accepts --output for artifact placement. The scope suite does not call a provider or production database. Browser/API tests use mocked MongoDB/provider/chart/PDF infrastructure. Production load, live database concurrency, PDF layout, broader real data and human usability are not established by these results.

## Limits

Natural-language qualifiers such as “last month”, “in North” or inline ISO dates are still refused by the question grammar. Use the explicit controls or API scope; the parser never guesses how such phrases should map to fields or bounds.

Relative dates, timezone conversion, fiscal calendars, overlapping windows, grouped period comparisons, conversion between currencies, arbitrary predicates and multi-dimensional analyses remain unsupported. Source completeness is not inferred. The tests are correlated, synthetic and developer-designed, and cover only the implemented analyst path, not independent correctness of every dashboard/ML/forecast component.

## Deliverables

- phase-8-summary.md: this report.
- phase-8-scope-final/*.json: final independent scope evaluation.
- phase-8-base-final/*.json and phase-8-language-final/*.json: prior-suite reruns.
- phase-8-results.csv: evaluation counts by suite/family.
- phase-8-example.json: a generated request, comparison and evidence.
- phase-8-scope-controls.png: browser screenshot of the new controls using synthetic data.
- phases-1-to-8-changes.patch: cumulative local implementation.
