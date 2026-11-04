# Simple annotation collection guide

## What to send

- Annotator A: `benchmark/collection/participant_packets/README.md`, `annotator_a/FORM.md`, `TRAINING_EXAMPLE.md`, assigned task cards, and a read-only source archive with its checksum.
- Annotator B: the same `README.md`, `annotator_b/FORM.md`, `TRAINING_EXAMPLE.md`, assigned cards, and the same read-only source archive. Do **not** send A’s completed work.
- Adjudicator: `README.md`, `adjudicator/FORM.md`, the source archive/checksum, and both locked completed forms. Do **not** send AURA-BI responses.

Use separate private folders outside Git, for example `private-submissions/annotator-a`, `private-submissions/annotator-b`, and `private-submissions/adjudicator`. Do not add completed forms, identities, or source snapshots to the repository.

## Import genuine forms

Convert each completed form to one JSON object per line following `benchmark/collection/annotator_form.json` and the adjudicator decision shape in `adjudication_form.json`. The coordinator separately prepares `inputs.jsonl` from the immutable source snapshot; inputs contain records/question/checksum but no labels.

```sh
python -m benchmark.collection.import_human_forms \
  --inputs private-submissions/inputs.jsonl \
  --annotator-a private-submissions/a.jsonl \
  --annotator-b private-submissions/b.jsonl \
  --adjudications private-submissions/adjudications.jsonl \
  --experiment-config private-submissions/experiment_config.json \
  --output private-submissions/staged-package
python -m benchmark.quality_control private-submissions/staged-package
python -m benchmark.freeze private-submissions/staged-package
```

The import deliberately creates `STAGED_PENDING_HUMAN_REVIEW`, not a frozen corpus. After a human study owner verifies authorship, consent/process records, source provenance, splits, and checksums, they may manually complete the manifest with `authorship: "external_human"` and a real `frozen_at` timestamp. Then rerun quality control and freeze. Never use the training example or developer task cards as submissions.
