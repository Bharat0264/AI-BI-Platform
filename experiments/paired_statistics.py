"""Cluster-aware paired summaries; refuses underpowered external studies."""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any, Callable


def paired_cluster_summary(rows: list[dict[str, Any]], score: Callable[[dict[str, Any]], float],
                           left: str, right: str, minimum_clusters: int = 3) -> dict[str, Any]:
    """Return paired cluster means without pretending correlated rows are iid."""
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[row["dataset_family"]][row["baseline"]].append(score(row))
    differences = [sum(group[left]) / len(group[left]) - sum(group[right]) / len(group[right])
                   for group in groups.values() if group.get(left) and group.get(right)]
    if len(differences) < minimum_clusters:
        return {"status": "NOT_RUN", "reason": "fewer than minimum paired dataset clusters",
                "paired_clusters": len(differences), "minimum_clusters": minimum_clusters}
    mean = sum(differences) / len(differences)
    variance = sum((x - mean) ** 2 for x in differences) / (len(differences) - 1)
    se = sqrt(variance / len(differences))
    return {"status": "DESCRIPTIVE_ONLY", "paired_clusters": len(differences), "mean_difference": mean,
            "normal_approx_95_ci": [mean - 1.96 * se, mean + 1.96 * se],
            "warning": "Use a prespecified cluster bootstrap for final inference; this helper is descriptive."}
