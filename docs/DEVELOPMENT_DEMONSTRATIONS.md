# UCI development demonstrations

Run `python -m experiments.development_demo_export`. Outputs are written to `outputs/paper_evidence/development/` as JSON and CSV and labelled `DEVELOPMENT_DEMONSTRATION_NOT_INDEPENDENT`.

The exporter reads three preserved UCI originals without mutation. It makes explicitly documented derived developer views: Online Retail derives gross sales (`Quantity × UnitPrice`) and a contrasting `Net Sales` proxy (`UnitPrice`); Online Shoppers renames Boolean `Revenue` to `Purchase Outcome` and uses `PageValues` as a developer arithmetic field; Bank Marketing copies euro `balance` to a developer `Revenue` field. These views demonstrate supported grammar and ambiguity behavior only; they are not validated business policies, benchmark cases, or external evidence.
