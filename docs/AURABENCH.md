# AURABench

AURABench is AURA-BI's deterministic heterogeneous-business-analytics benchmark. It currently generates synthetic retail, finance, human-resources, supply-chain, marketing, e-commerce, manufacturing, and energy datasets. Each family carries schema-role labels, applicable KPI labels, analytical-question labels, answerability labels, expected operations/source columns, and an injected anomaly location.

Schema perturbation levels are L0 original, L1 synonym renaming, L2 abbreviation renaming, L3 opaque names, L4 irrelevant/noise fields, and L5 mixed adversarial perturbation. Perturbations are seeded and retain an original-to-perturbed mapping; they never alter the analytical ground truth.

`B0_STATIC_BI`, `B2_SEMANTIC_ONLY`, `B3_EVIDENCE_AURA`, and `B4_FULL_AURA_BI` are executable deterministic adapters. `B1_DIRECT_LLM` is recorded as skipped unless an explicitly configured provider-backed direct baseline is available; it is never silently replaced by a deterministic system.

Implemented benchmark measurements include semantic accuracy/macro/per-role F1, KPI precision/recall/F1, answerability, task and numeric correctness, grounding rates, anomaly precision/recall/F1, latency, repair frequency, and Schema Perturbation Robustness Score inputs. Benchmark output is measured at run time, not committed as a claimed result.
