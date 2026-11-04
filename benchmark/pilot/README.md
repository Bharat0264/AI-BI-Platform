# AURA-BI human-evaluation pilot

Status: **WAITING_FOR_HUMAN_PARTICIPANTS**. This package contains 30 developer-authored task-design cards (10 per UCI source), not evaluation questions, answers, labels, or human annotations. Each participant independently authors or reviews a question against a read-only source snapshot, then records uncertainty and labels in their private form.

Role folders are intentionally separate. Distribute only `annotator_a/` to pseudonym A and only `annotator_b/` to pseudonym B. Do not place submissions in these folders. A coordinator stores submissions in restricted, write-once locations; the adjudicator receives them only after both are locked.

The source archives stay in `benchmark/collection/raw/` and are git-ignored. Their hashes and field metadata are in `../collection/acquisition_manifest.json`.
