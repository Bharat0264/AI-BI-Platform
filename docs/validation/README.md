# Validation evidence

Raw measured evaluation/audit records accompany the final source delivery. The release summary links these results to their environment and source hashes; do not substitute documentation constants for executing checks.

- arithmetic.json: seeded independent-reference synthetic arithmetic/safe-refusal cases.
- language.json: whole-question language and unsupported-qualifier cases.
- scope.json: independent row-scope/date-comparison references.
- public-data.json: historical UCI public-data checks. All configured metadata tasks pass; three unassisted opaque-column questions still require user semantic confirmation.
- retail-amount.json: supplemental explicitly declared Quantity × UnitPrice calculation, with signed returns/adjustments retained; not audited profit or booked revenue.
- dependency-audit.json: full installed-environment scanner result for the fresh Python 3.12 environment, including development tools.
- public-source-attribution.json and retail-provenance.json: source licensing/attribution and official/local retail equivalence under the declared normalization rule.

These are developer-authored checks. Cases are correlated and do not represent independent statistical samples, a user study or production validation. Public tasks use every row but only declared task columns; semantic metadata is explicit. Runtime/audit results may differ on another platform or after dependency updates. No raw uploaded source data, credentials, production database contents or private account data are included here.

render-startup.json records the subsequent Render binding/cache-recovery fix and its 405-test regression run. The earlier summary.json is the pre-fix phase-completion snapshot.

public-demo.json records the owner-requested temporary no-login mode, its isolation/reversal behavior and the 410-test regression run.
