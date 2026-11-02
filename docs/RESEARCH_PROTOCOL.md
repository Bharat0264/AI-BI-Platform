# Research protocol: ambiguity-aware, evidence-verified business analytics

Status: implemented prototype and preliminary reproducible study, 2 November 2026. Not a peer-reviewed paper, preregistration, or proof of novelty.

## Research question and scope

Can showing verified results for detected alternative measure meanings preserve answer safety while giving more inspectable evidence than clarification alone?

Example: `What is sales?` over Gross Sales and Net Sales. A number can be arithmetically correct but answer the wrong business question. The system computes each detected interpretation, labels it conditional, compares the requested output, and asks the user to choose. Equal numerical outputs do not prove equal business meaning. The dashboard is a demonstration interface for this method.

Fields: natural-language data interfaces, semantic ambiguity, data provenance, and selective answering. Primary contribution under investigation: a bounded, auditable comparison of the consequences of alternative business measure definitions. This is a candidate engineering contribution, not an established novel algorithm.

## Hypotheses and alternatives

H1: Conditional evidence reduces unjustified unconditional answers compared with choosing the first detected candidate.
H2: Conditional evidence exposes complete, numerically correct alternatives more often than clarification without computed evidence.
H3 (untested): Non-expert users choose the intended definition more accurately with conditional evidence than with column names alone.

Choose the existing deterministic conditional method for the prototype: reproducible and auditable, but limited to supported grammar and detected candidates. A direct LLM baseline would broaden language coverage but requires a fixed model/version, prompts, budget, and repeated runs. It has not been evaluated in this study. Clarification alone is a valid safe alternative with less computation and less numerical context; the study does not show it is worse for users.

## Executed study

Run from repository root with Python 3.12 and installed dependencies:

```sh
python -m experiments.research_study --output docs/validation/research-policy-study.json
python -m pytest tests/test_research_study.py -q
```

The runner uses 332 existing developer-designed synthetic cases, ten seeded datasets and fixed adversarial fixtures. A separate Decimal implementation checks arithmetic. Ground truth contains expected status, measure, operation, groups, and alternatives. It is implementation-independent arithmetic, not independent research authorship.

Three paired output-policy ablations share the same parser, candidate detector, computation and verifier: choose first candidate; clarify without evidence; retain conditional evidence. The first two are post-hoc transformations of full-system responses. They do not independently measure candidate discovery, runtime, or end-to-end baseline performance. This isolates presentation/selection policy, but favors no claim about competing systems.

| Policy | Answerable cases resolved | Unsafe unconditional answers | Complete correct conditional responses |
| --- | --- | --- | --- |
| First candidate | 243/243 | 10/332 | 0/10 |
| Clarification only | 243/243 | 0/332 | 0/10 |
| Conditional evidence | 243/243 | 0/332 | 10/10 |

Raw per-case outputs, errors, seeds, Python version, base commit and source hashes are in [the measured artifact](validation/research-policy-study.json). The remaining 79 cases are expected refusals. Unsafe means returning an unconditional `OK` where the ground-truth contract requires clarification or refusal; it does not necessarily mean arithmetic is wrong. The contract-pass metric requires computed alternatives for ambiguous cases and therefore penalizes clarification-only by construction. It is not a neutral overall utility score. Safety and conditional completeness are reported separately above.

Confirmed: these outcomes occurred on this suite. Likely: conditional evidence can expose the practical consequences of detected semantic ambiguity. Uncertain: usefulness to real users, external generalization, and research novelty.

## Threats to validity and failure modes

This is retrospective evaluation on regression cases used during development, not held-out validation. Templates and seeded variants are correlated; no significance test or confidence interval is appropriate here. Only ten cases in this run require ambiguity clarification. No SQL joins, unrestricted language, multiple tables, comprehensive business policies, or human intent inference are evaluated. A detector can miss a plausible interpretation. The system caps comparison at 32 candidates and must report partial coverage. Identical totals can conceal different grouped or ranked results. Zero observed unsafe answers does not establish universal safety. Existing public-data checks are supplementary and not an independent competitive benchmark.

## Next study, before any publication claim

1. Freeze this protocol and code before collecting new test data. Keep existing cases as development data.
2. Recruit two independent annotators to write and label new questions on at least three licensed domains; record disagreements and adjudication. Split by source dataset and question template, not random rows. Obtain permissions and protect business data.
3. Include equal-total/different-group cases, missing meanings, units/currencies, unsupported scope, more than 32 candidates, and misleading column names. Report every exclusion and failure.
4. Compare independent end-to-end implementations: first-match semantics, clarify-only, full conditional method, and a fixed-version LLM baseline. Ablate candidate detection, explicit definitions, comparison, and verification separately. Never pass expected answers into a baseline.
5. Measure unsafe-answer rate, correct resolved coverage, candidate precision/recall, conditional numerical correctness, latency, computation cost and clarification burden. Publish denominator and raw cases. Use paired differences and dataset/template-cluster bootstrap intervals only with enough independent clusters; do not treat generated rows as independent observations.
6. Test H3 in a counterbalanced user study with a prespecified primary endpoint: correct definition selection. Also measure task time and understanding. Do not claim improved usability before collecting those observations.

## Related work and novelty boundary

- Bhaskar, Tomar, Sathe and Sarawagi, *Benchmarking and Improving Text-to-SQL Generation under Ambiguity*, EMNLP, December 2023: ambiguity and multiple valid interpretations are established research topics. [Paper](https://aclanthology.org/2023.emnlp-main.436/) and [authors' code](https://github.com/testzer0/AmbiQT).
- Ding et al., *AmbiSQL: Interactive Ambiguity Detection and Resolution for Text-to-SQL*, submitted August 2025, revised March 2026: interactive clarification already exists. [Paper v2](https://arxiv.org/abs/2508.15276v2).
- Geifman and El-Yaniv, *Selective Classification for Deep Neural Networks*, NeurIPS 2017: abstention trades coverage against error. This motivates reporting both; it does not supply a guarantee for our deterministic BI method. [Paper](https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html).
- *Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows*, 2024 preprint / ICLR 2025: enterprise workflows are a substantially broader target than this single-table prototype. [Paper](https://arxiv.org/abs/2411.07763).

Targeted literature review, not an exhaustive systematic review. No published benchmark scores were compared with our different dataset. No claim of first invention or state-of-the-art performance is justified.
