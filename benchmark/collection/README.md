# Annotation-ready external collection package

This directory contains no evaluation examples and no claimed labels. It is a role-separated template for externally collected cases.

Create one private workspace per annotator from `annotator_form.json`. Do not share those workspaces until both submissions are locked. A coordinator alone copies source snapshots and questions into `inputs.jsonl`; annotators submit their records to a restricted `labels/annotator-<id>.jsonl` location. An adjudicator sees the two submissions and writes `adjudications.jsonl`. The experiment runner receives only the frozen `inputs.jsonl`; scoring receives hidden labels only after baseline execution.

Use `dataset_registry.json` as a procurement checklist. Every entry is `PENDING_PROVENANCE_VERIFICATION`; none is a verified public dataset or an evaluation case.
