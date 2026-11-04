"""Matched evaluation runner for a frozen external annotation package.

The runner records NOT_RUN rather than substituting developer fixtures when no
external package has been collected.  Baselines receive only FrozenCase inputs;
gold labels are used after execution for scoring.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmark.independent import load_frozen_package
from experiments.fair_baselines import BASELINES, execute


def run(package: str | Path) -> dict[str, Any]:
    try:
        cases, labels, manifest = load_frozen_package(package)
    except (FileNotFoundError, ValueError) as exc:
        return {"status": "NOT_RUN", "reason": str(exc), "baselines": list(BASELINES),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "protocol": "external-human-frozen-v1"}
    traces = []
    for case in cases:
        for baseline in BASELINES:
            observed = execute(case, baseline)
            # Labels are deliberately joined only after the baseline terminates.
            gold = labels[case.case_id]
            traces.append({"case_id": case.case_id, "dataset_family": case.dataset_family,
                           "template_family": case.template_family, "baseline": baseline,
                           "observed": observed, "gold": gold})
    return {"status": "COMPLETED", "protocol": "external-human-frozen-v1", "manifest": manifest,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": {"python": sys.version, "platform": platform.platform()}, "traces": traces}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.package)
    Path(args.output).write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": result["status"], "reason": result.get("reason")}, indent=2))


if __name__ == "__main__":
    main()
