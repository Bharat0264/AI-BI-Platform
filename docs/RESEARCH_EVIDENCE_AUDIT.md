# Research evidence audit — 2026-11-04

## Implemented components

The repository contains a deterministic single-table semantic/question pipeline (`aura/core.py`, `aura/questions.py`, `aura/scoped_engine.py`), application-specific evidence and provenance (`aura/provenance.py`, `aura/verifier.py`), SIIE (`aura/impact.py`), EVVE (`aura/visualization_engine.py`), and dashboard consistency checks (`aura/dashboard_consistency.py`). Existing Flask and Plotly functionality remains unchanged.

The original study in `experiments/research_study.py` and `docs/validation/research-policy-study.json` is a reproducible developer-authored regression/policy study. `experiments/accuracy.py` and historical AURABench artifacts are useful engineering checks, not independent validation. `benchmark/evaluation.py` is now explicitly labeled development stress data. It formerly used the word “heldout,” which only described a code split and risked overstatement.

## Current evidence and gaps

| Topic | Evidence status | Limitation |
| --- | --- | --- |
| Arithmetic/evidence binding | Implemented and regression-tested | Binding verification is not independent confirmation of business truth. |
| Ambiguity impact | SIIE tests and developer stress fixtures | Candidate labels are not externally authored. |
| Chart contracts | EVVE valid/invalid contract tests | No frozen independently labeled chart corpus. |
| Dashboard consistency | Adversarial tests | No independently labeled dashboard corpus. |
| Baselines | B0–B5 adapters exist | B0–B4 have not been measured on external frozen cases; B1/B2 remain simplified policy adapters and B3/B4 share code. |
| LLM baseline | Provider-gated adapter | Not run without fixed permitted credentials/model/version. |
| Statistical inference | Underpowered-safe helper | No independent dataset/template clusters exist. |

## Leakage and contamination controls

The historic fixtures and their expected labels reside together in developer-controlled source code. They must not be loaded by an independent runner. The new `benchmark.independent` loader requires an `external_human` frozen manifest, separates `inputs.jsonl` from `labels.jsonl`, rejects label fields in inputs, validates per-snapshot SHA-256 hashes, and does not fall back to developer data.

## Claims supported today

Supported: the documented deterministic components exist; their focused unit/contract tests execute; the historical policy-study artifact records the stated results on its own developer suite.

Unsupported: independent generalization, fair baseline superiority, statistical significance, visualization/dashboard detection accuracy, user benefit, novelty, state of the art, causal explanations, or IEEE submission readiness.
