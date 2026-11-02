# Phase 7: Meaning-preserving question parsing

Implemented and evaluated locally on 2 November 2026. No commit, push or deployment performed.

## Results

| Evaluation | Previous | Now |
|---|---:|---:|
| Original synthetic matrix | 262/332 | 332/332 |
| Original ordinary-phrasing cases | 10/80 | 80/80 |
| Supplementary language checks | Not run in Phase 6 | 154/154 |
| Unsafe unconditional answers in evaluated sets | 0 in the original matrix | 0 original; 0 supplementary |

All 243 returned answers to answerable cases in the original matrix, and 24 in the supplementary matrix, matched independent Decimal-based arithmetic. The original case IDs, questions, expected statuses and numerical expectations were verified unchanged from the Phase 6 run.

These are developer-authored, synthetic specification and regression cases. Their failures informed the implementation. They are not a blinded held-out test or evidence of general language understanding, real-world accuracy or competitive superiority.

## What changed

- Added aura/questions.py: a frozen typed QuestionIntent plus named, full-question grammar rules.
- Recognizes totals, averages, breakdowns and highest/lowest grouped amounts in common phrasing, including polite requests and the contraction “what’s”.
- Recognizes detected custom grouping column names under supported region/category roles, rather than requiring literal “region” or “category”. An exact grouping name can resolve multiple columns with the same role.
- Supports highest/lowest group averages when the question explicitly requests average/mean, preserving the aggregation in calculations, definitions and evidence.
- Records the parsed measure alias, aggregation, grouping alias, direction, rule and normalized question in the plan. Existing View Evidence exposes this plan.
- Rejects conflicting normalized column roles rather than allowing column order to choose a business meaning.
- Preserves semantic corrections, saved-definition scope/version, exact-column precedence, conditional interpretations, unit guards and freshness/replay behavior.

## Examples now supported

| Question | Explicit interpretation |
|---|---|
| How much revenue did we earn? | Sum of the selected revenue column across supplied rows |
| Show me revenue for each region | Revenue sums grouped by region |
| Give me the average revenue per region | Mean of valid revenue rows within each region |
| Which region earned the most revenue? | Region with the highest summed revenue, with ties disclosed |
| What is the minimum regional revenue? | Region with the lowest summed revenue |
| Which category has the lowest average profit? | Category with the lowest mean row-level profit |
| List revenue by region | Grouped revenue sums, not a listing of raw records |
| Which region brought in the most revenue? | Highest grouped revenue sum; “brought in” is a named earning verb |
| Can I see total revenue? | Revenue total across supplied rows |
| Show revenue by Market | Grouped sums using an unambiguous detected Market column |

“Across all regions/categories” means an unfiltered total over the supplied rows. It does not assert that the upload contains every region in the world or company. Average means row-level arithmetic mean, not a weighted average or average of group totals. These choices are inspectable in the plan and definition; the parser does not infer entity grain.

## How unsupported meaning is protected

The parser matches complete supported forms. It never extracts a familiar measure and ignores the remainder. Unknown remaining words, conflicting parses or unsupported operators produce INSUFFICIENT DATA.

- Explicit guards reject unsupported periods, filters, forecasts, ratios, percentages, causes and multi-objective requests.
- “In” is accepted only as part of the named earning verb “brought in”, not as a location/date filter.
- Courtesy words are handled only in controlled positions. Internal punctuation/operators and arithmetic expressions are not stripped into a simpler amount question.
- Hyphens and formula punctuation in question text are conservatively rejected. A hyphenated/underscored column can be referred to using its unambiguous space-normalized label, provided it has no blocked qualifiers.
- Ambiguous requests such as “best region”, “minimum revenue by region” or “average regional revenue” remain unsupported. Specify the grouping and whether you mean totals or averages.
- The question parser has a 2,000-character limit, uses escaped schema aliases and never generates SQL or executes user text.

Date and region/category filtering are still unavailable in the analyst question endpoint. Dashboard filters remain separate. Currency conversion, arbitrary formulas, multi-dimensional groupings and open-ended reasoning are not added.

## Additional checks

The 154-case supplementary matrix contains:

- 20 explicit language specifications, including grouped averages, ranking averages, contractions, polite wording and exact alternate column names.
- 120 minimal-pair checks made by adding unsupported time, location, exclusion, forecast or threshold qualifiers to those questions.
- 4 additional ordinary-phrasing challenges. The first run exposed all four as gaps; named grammar rules then addressed them. Their final success is development/regression evidence, not held-out generalization.
- 10 unsupported or ambiguous intents covering operators, percentages, causes, vague rankings and multiple objectives.

The same small synthetic table underlies these checks. They are strongly correlated; no inferential confidence intervals or population-level accuracy estimates are claimed.

## Validation

- Full regression suite: **292 passed in 32.16 seconds**, including 8 real-browser tests.
- The new browser test asks an ordinary-phrasing question, confirms a Sales definition, asks a grouped paraphrase, and verifies that an exact Gross Sales question still overrides the Net Sales default.
- Both independent evaluation suites completed without unexpected exceptions.
- Legacy benchmark smoke completed, and git diff --check passed.
- Scripted browser tests use mocked MongoDB/provider/chart/PDF infrastructure, as documented in the earlier interface phase. No real-user usability study or production concurrency/load test is claimed.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe experiments/accuracy.py
.\.venv\Scripts\python.exe experiments/accuracy.py --suite language
```

Use --output to choose an artifact directory. Raw reports include expected and actual structured outputs, case IDs, failures, seeds, source hashes and runtime metadata. The extra language fixtures live in experiments/language_checks.py. Scoring still uses the independent oracle in experiments/oracle.py.

## Deliverables and next work

- phase-7-summary.md: this report.
- phase-7-final/*.json: final original-matrix run.
- phase-7-language-final/*.json: final supplementary language run.
- phase-7-comparison.csv: before/after results.
- phase-7-examples.json: generated examples with parsed plans and evidence.
- phases-1-to-7-changes.patch: cumulative local implementation.

The question language remains a bounded deterministic grammar and can reject other valid English phrasings. Next, add explicit, verified filter and date-comparison plans rather than weakening qualifier guards. Broader real-data and human usability evaluation remains necessary.
