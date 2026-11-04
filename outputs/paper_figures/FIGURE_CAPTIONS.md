# AURA-BI Figure Captions

All figures use a white background, accessible semantic colors, and code-native editable Mermaid sources. Figures 3, 9, 10, and 13 explicitly distinguish completed developer engineering evidence from pending independent evaluation and unverified deployment.

| Figure | IEEE-style caption | Suggested placement | Supporting implementation / records |
|---|---|---|---|
| 1 | **AURA-BI system architecture.** The legacy Flask application path is distinguished from the additive evidence-verified research workflow. | Double column; System Architecture | `server.py`, `aura/core.py`, `aura/research_pipeline.py`, `aura/visualization_engine.py`, `aura/dashboard_consistency.py`, `app/report_generator.py` |
| 2 | **Implemented question-processing pipeline.** Deterministic schema grounding, planning, computation, and evidence verification precede any optional non-authoritative narration. | Double column; Methodology | `aura/core.py`, `aura/verifier.py`, `aura/interpretations.py` |
| 3 | **Research methodology and evidence status.** Dataset preparation and developer checks are complete; independent annotation, freeze, and matched evaluation remain pending. | Double column; Experimental Setup | `benchmark/`, `docs/INDEPENDENT_EVALUATION_PROTOCOL.md`, `outputs/paper_evidence/` |
| 4 | **Semantic Interpretation Impact Engine (SIIE).** Each admissible definition is independently computed and compared before clarification is required. | Single column; Methodology | `aura/impact.py`, `aura/interpretations.py` |
| 5 | **Deterministic evidence-verification flow.** Evidence binds source data, scope, operation, result, and claim verification. | Single column; Methodology | `aura/verifier.py`, `aura/provenance.py` |
| 6 | **Evidence-Verified Visualization Engine (EVVE).** Chart contracts are validated against evidence, series, scope, and provenance. | Single column; Methodology | `aura/visualization_engine.py` |
| 7 | **Cross-dashboard semantic consistency verification.** Declared comparable components are checked for compatible semantics and scope. | Single column; Methodology | `aura/dashboard_consistency.py` |
| 8 | **Selective publication decision tree.** The unified pipeline gives unresolved ambiguity precedence, then blocks invalid evidence or non-publishable consistency. | Single column; Safety Methodology | `aura/research_pipeline.py`, `aura/dashboard_consistency.py` |
| 9 | **Configured deployment architecture.** This is an implementation diagram only; no live deployment is claimed. | Single column; Implementation | `start.py`, `server.py`, `docs/DEPLOYMENT_VALIDATION.md` |
| 10 | **Prespecified independent comparison design.** Frozen human-authored data and paired B0–B4 execution are pending. | Double column; Experimental Setup | `benchmark/freeze.py`, `experiments/independent_evaluation.py` |
| 11 | **Verified report provenance.** A publishable research report couples analytical evidence and chart contracts to a machine-readable manifest. | Single column; System Architecture | `aura/research_pipeline.py`, `app/report_generator.py`, `server.py` |
| 12 | **Illustrative developer safety case.** Alternative sales definitions can change values, rankings, and chart shapes, requiring clarification rather than selection. | Single column; Case Study | `outputs/paper_evidence/development/ambiguity_outcomes.json`, `aura/impact.py` |
| 13 | **Measured developer-only engineering checks.** Results come from reproducible development fixtures, not independent evaluation. | Double column; Engineering Validation | `outputs/paper_evidence/development/*.json`, `outputs/paper_evidence/provenance/experiment_metadata.json` |

## Technical notes

- Every `*.mmd` file is the editable structural source for its SVG/PDF/PNG counterpart. Re-run `python experiments/generate_paper_figures.py` with the supported environment to regenerate the collection.
- Figure 13 is sourced only from real development records: `deterministic_correctness.json`, `ambiguity_outcomes.json`, `evve_outcomes.json`, `dashboard_outcomes.json`, and `component_timings.json`. It intentionally excludes independent baseline, ablation, and live-deployment claims because those measurements do not exist.
- Figure 12 is illustrative and developer-derived; it is not evidence of human-annotated interpretation accuracy.
