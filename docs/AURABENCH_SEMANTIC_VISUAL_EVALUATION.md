# AURABench semantic-impact and EVVE evaluation

This package is separate from `experiments/accuracy.py` and `experiments/research_study.py`. Those are developer-authored regression/development studies and must not be described as independent validation.

Run:

```sh
python -m experiments.semantic_visual_benchmark --output outputs/experiments/semantic-visual.json
python -m pytest tests/test_semantic_visual_benchmark.py -q
```

The output contains raw case/ablation records, split manifest, dependency versions, resource maximum RSS, latency, configuration, and measured summaries. Figures and statistical intervals are intentionally deferred: the current small correlated synthetic fixture design does not support statistical significance or publication-quality comparative claims. Generate figures only from a frozen measured output after independently authored, dataset- and template-separated cases provide enough clusters for paired bootstrap intervals.

The held-out synthetic cases cover unambiguous metrics, ambiguous definitions, equal totals with different breakdowns, ranking reversals, currency/unit hazards, corrupted values, misleading schemas, unsupported requests, and an explicit development-only split. EVVE incorrect-specification and dashboard-version/freshness cases remain in their own test modules until independently authored/frozen benchmark cases are added.

Threats: fixtures are synthetic and correlated; the current split labels do not make their authorship independent; no external public dataset is included here; semantic candidate annotations and visualization/dashboard gold labels are incomplete. The runner reports unavailable metrics as `not_measured`, never as zero or success.
