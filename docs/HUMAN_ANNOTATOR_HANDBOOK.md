# AURA-BI independent benchmark annotator handbook

You are labeling business questions against a frozen source snapshot, not judging AURA-BI. Do not run the system, inspect its responses, consult another annotator, or infer intended labels from column names alone.

For each case, first determine whether the request is answerable from the stated snapshot. Use `INSUFFICIENT_DATA` for unsupported requests such as causal explanations, absent fields, incompatible currency/unit without an authorized conversion policy, or unavailable temporal scope. Use `CLARIFICATION_REQUIRED` when two or more defensible definitions remain. Do not select an interpretation because it yields a preferable value.

Record the intended business definition and every admissible alternative, including source columns, formula, currency/unit, and rationale. Independently calculate aggregate, grouped values, rankings, extrema, and requested differences using a spreadsheet or a separate Decimal calculation; record the method. A total agreement does not remove an ambiguity if breakdowns, ranks, or chart shape differ.

For visualization, name an appropriate chart type only when the data supports it and say whether the supplied specification preserves categories, aggregation, filters, scope, units, axes, and values. For dashboard cases, identify only semantic/descriptive contradictions supported by components and their declared scope; do not infer causal root causes.

Complete `benchmark/collection/annotator_form.json` independently. Submit it through the coordinator’s private channel. Your record will be immutable after submission; corrections are appended, never overwritten.
