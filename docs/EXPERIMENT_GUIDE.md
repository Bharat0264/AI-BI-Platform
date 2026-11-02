# Experiment Guide

Run a deterministic smoke check with `python experiments/run_all.py --mode smoke --seed 42`. It evaluates retail/L0/full AURA-BI and writes actual raw JSON, CSV tables, and figures below `outputs/experiments/`.

Use `--mode small` for eight domains, one seed and all schema perturbation levels. Use `--mode full` for the five default seeds, all domains, baselines and ablations. Full mode is intentionally not run as part of ordinary development. See [AURABench](AURABENCH.md) and [reproducibility](REPRODUCIBILITY.md).

For the current ambiguity research, run python -m experiments.research_study --output outputs/research/policy-study.json. See [protocol and limitations](RESEARCH_PROTOCOL.md). This paired output-policy study is separate from the older AURABench experiments.
