# Phase 9: Public real-data validation

Implemented and executed locally on 2 November 2026. No commit, push or deployment performed.

## Direct result

- Main real-data checks improved from **21/32 to 29/32**. The same task IDs, questions and numerical references were retained.
- All **23/23 metadata-configured tasks** passed.
- All **4/4 supplemental declared retail line-amount checks** passed.
- **3 cold-start gaps remain**: unassisted quantity questions on daily/hourly `cnt` and bank `campaign` need explicit semantic confirmation. No incorrect resolved numerical answer or unsafe unconditional answer occurred in the main evaluated cases.
- Full regression suite: **347 passed in 27.14 seconds**, including 12 real-browser tests.

These are developer-authored checks on historical public data. They are not a real-user study, independent authorship, production certification or evidence of world-leading accuracy.

## Verified sources and actual file sizes

| Table | Source release | Rows read | Original columns | Task columns |
|---|---|---:|---:|---|
| day | bike | 731 | 16 | dteday, cnt, season, workingday |
| hour | bike | 17,379 | 17 | dteday, cnt, season, workingday |
| bank | bank | 45,211 | 17 | campaign, job, month |
| retail | retail | 541,909 | 8 | Quantity, InvoiceDate, Country |

The four tables come from three UCI releases. Daily and hourly bike tables represent overlapping underlying activity; they are not independent populations. All rows were retained. The engine received declared task-column projections, so this is not a full-width production load test.

Official attribution, pages and licenses:

- Hadi Fanaee-T (2013), [Bike Sharing](https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset), DOI [10.24432/C5W894](https://doi.org/10.24432/C5W894). Counts from Capital Bikeshare in 2011–2012. CC BY 4.0.
- S. Moro, P. Rita and P. Cortez (2014 dataset citation), [Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing), DOI [10.24432/C5K306](https://doi.org/10.24432/C5K306). The selected bank-full.csv is the older 45,211-record variant, not bank-additional-full.csv. CC BY 4.0.
- Daqing Chen (2015), [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33). UK retailer transaction data from 2010–2011. CC BY 4.0.

License: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Source pages were checked on 2 November 2026. Archive URLs, exact byte sizes and SHA-256 checksums are pinned in benchmark/real_sources.json and copied to phase-9-source-card.json.

The current bike catalog page lists 17,389 instances, while the downloaded hour.csv has 17,379 data rows. The evaluation uses the actual file and checksum. It does not invent ten additional rows to match catalog metadata.

## Local-file provenance and quality audit

The repository's data/data.csv was compared with the official Online Retail workbook across all 541,909 rows and all eight columns. It matches under a declared representation normalization: source row/column order; dates represented as ISO seconds; Decimal text for Quantity/UnitPrice/CustomerID; empty cells represented as empty strings; other strings retained exactly. The local encoding was explicitly cp1252 and its dates MM/DD/YYYY HH:MM. This establishes value equivalence under that rule, not byte identity or the full history of how the local CSV was originally produced.

Canonical hash: `3a30d32b81eda7a2b150b7825b96e34ca4330442558bab874cec842ea53d20f6`.

Measured empty cells in both official and local representations: **135,080 CustomerID cells and 1,454 Description cells**. This differs from the catalog's no-missing marker. No rows were dropped to hide those missing fields. Returns, cancellations, adjustments and duplicate records were not removed. Results describe the source records, not deduplicated economic events or audited bookkeeping truth.

The other repository retail/Superstore files have no verified provenance in this work. They were inventoried but excluded from claims about observed real-world data. No original repository CSV was rewritten.

## Failures exposed and fixes

1. **Semicolon CSV input.** The bank file previously parsed as one column instead of 17. CSV loading now checks a bounded sample for comma, semicolon, tab or pipe delimiters and handles quoted values. It records the selected delimiter/encoding. A comma fallback is recorded when no reliable alternative is detected; sniffing is not a guarantee for arbitrary malformed formats.
2. **Legacy encodings and categorical codes.** The loader handles UTF-8/BOM, cp1252 and Latin-1 fallback. Only empty CSV cells are treated as missing; literal NA/NULL category labels survive. The source bytes remain unchanged.
3. **Explicit retail date representation.** Scope controls/API now support ISO or explicit month/day and day/month date/time formats. The real retail CSV's month/day timestamps can be compared without external source rewriting. Unknown formats are rejected, and omitting the format still rejects ambiguous non-ISO dates. The selected format is recorded in evidence and replay.
4. **Non-financial import path.** General datasets can now be imported for Data Intelligence and AI Analyst without requiring a financial dashboard. They receive no synthetic sales/profit metrics or forecast. This prevents bike record indices being selected as sales and missing profit being presented as a measured zero.
5. **Financial-only paths.** The shared preparation path, financial report and related financial views reject general datasets. General CSV exports retain source columns; the financial PDF returns an informative 400 when its required revenue/profit/date schema is absent. Explicit Total Amount monetary naming is recognized, rather than falling back to an unrelated numeric field.
6. **General previews.** Missing/non-finite preview values produce valid JSON. General imports are labelled untransformed, date validity unassessed and quality score N/A; they are not advertised as cleaned or financially complete.

These fixes do not constitute a full audit of every legacy financial dashboard assumption, discount estimate, forecast, AutoML component or recommendation.

## Metadata versus cold start

For bike data, publisher metadata establishes cnt as rental count, dteday as date and season/workingday as categorical codes. For bank data, campaign is a count of contacts recorded for a source row, job is categorical, and month alone is not a complete calendar date. Retail Quantity, InvoiceDate and Country retain their documented meanings.

The configured cases provide these mappings explicitly through the same correction mechanism available in the product. They do not train hard-coded cnt/campaign aliases into the engine. A sum of bank campaign values is a sum over records, not a verified count of unique calls or unique clients. Bike means are per recorded day/hour row, not necessarily per complete calendar interval.

The three unassisted cases remain INSUFFICIENT DATA until the meaning is confirmed. Automatic semantic onboarding is therefore still a coverage limitation; the configured score must not be described as fully autonomous accuracy.

## Declared monetary supplement

The supplemental four checks use a derived copy with **Line Amount = signed Quantity × UnitPrice**, with GBP explicitly declared from the publisher's sterling unit. Pandas multiplication in the engine input is checked against independently computed Decimal multiplication from the original CSV values, followed by independent totals, means, country groups and a UK January 2011 versus December 2010 comparison.

All source rows are retained, including cancellations and adjustments. This is a declared line-amount calculation, **not profit, audited net sales or booked revenue**. The application has not gained an automatic formula-inference feature; the supplement is a documented derived-input validation.

## Validation and scope

- Main matrix: 32 checks, same before/after expectations; ingestion shape is validated before running calculations on a malformed frame.
- Configured numerical results use independent Decimal arithmetic and Python date/row selection, not the engine verifier's own status.
- Supplemental monetary checks: 4/4, with no invented profit or exchange conversion.
- Earlier synthetic checks still pass: 332/332 base, 154/154 language and 70/70 scope cases; legacy smoke completed.
- Regression suite: 347 passed, including browser import of a representative semicolon fixture, role confirmation and asking questions; explicit source-format selection and period comparison; and existing definition/lifecycle controls.
- Browser/API tests use mock MongoDB/provider/chart/PDF infrastructure and small representative fixtures. The complete public datasets were evaluated offline through the shared CSV loader and analyst engine with projected columns, not uploaded end-to-end through a production browser/database stack.
- No human usability study, production concurrency test, broad financial-model audit or competitive comparison was performed. Security/performance, user testing and production deployment are still the next three phases.

## Reproduce

From the checkout, install requirements-dev.txt, then:

```powershell
python scripts/fetch_validation_data.py --download --cache work/validation-public --verify-local-retail data/data.csv
python experiments/real_data.py --cache work/validation-public --local-retail data/data.csv
python experiments/retail_amount.py --source data/data.csv
python -m pytest tests -q
```

Network download is explicit. After preparation, the real-data runner works from the pinned cache without provider/database calls. The fetcher verifies archive checksums, reads only named archive members and preserves raw files. The XLSX-to-CSV derivative is declared and verified against pinned canonical values. If the local retail file is unavailable, omit --local-retail for the main suite to use the official ISO derivative; the recorded date-format compatibility run specifically used the verified local CSV.

Raw reports are timestamped, record source/code hashes and preserve failures. Cases reuse the same tables, so no independent-sample confidence interval or generalization estimate is claimed. Package versions for this session are saved in phase-9-environment.json.

## Deliverables

- phase-9-summary.md: this report.
- phase-9-before/*.json and phase-9-after/*.json: comparable real-data runs.
- phase-9-line-amount/*.json: separate monetary supplement.
- phase-9-source-card.json: attribution, license and checksum metadata.
- phase-9-local-provenance.json: complete-file canonical verification and missing-cell counts.
- phase-9-results.csv and phase-9-remaining-gaps.csv: score and remaining-failure tables.
- phase-9-real-format-control.png: an illustrative browser fixture screenshot, not an actual business result.
- phases-1-to-9-changes.patch: cumulative local implementation.
