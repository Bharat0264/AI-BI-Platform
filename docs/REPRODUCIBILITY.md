# Reproducibility

Install dependencies, then run:

```powershell
python -m pytest tests -q
python experiments/run_all.py --mode smoke --seed 42
python experiments/run_all.py --mode small --seed 42
python experiments/run_all.py --mode full
```

Each run writes timestamped raw JSON to `outputs/experiments/raw/`, CSV tables to `outputs/experiments/tables/`, and 300-DPI PNG figures to `outputs/experiments/figures/`. Raw records include an experiment ID, timestamp, Git SHA when available, seed, family, row count, perturbation, baseline, ablation, provider availability, metrics, latency, and repair frequency.

The full mode uses seeds `42, 123, 456, 789, 2026`, all benchmark domains, perturbations, baselines, and ablation flags. It may take substantial time. Provider credentials are optional; unavailable provider baselines are recorded as skipped rather than assigned synthetic scores.
