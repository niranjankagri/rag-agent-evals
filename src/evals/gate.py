"""The quality gate: averages per suite, compared with the limits in configs/quality_gate.toml."""

from dataclasses import dataclass

from evals.suites import CaseResult


@dataclass(frozen=True)
class GateRow:
    suite: str
    metric: str
    value: float | None
    limit: float
    passed: bool


def averages(results: list[CaseResult]) -> dict[str, float]:
    """The mean of each metric, over the cases that have it."""
    collected: dict[str, list[float]] = {}
    for result in results:
        for name, value in result.metrics.items():
            collected.setdefault(name, []).append(value)
    return {name: sum(values) / len(values) for name, values in collected.items()}


def check(suite: str, results: list[CaseResult], limits: dict) -> list[GateRow]:
    """One row per limit. A missing metric fails, so a renamed metric can't quietly pass."""
    rows = [
        GateRow(suite, "cases", float(len(results)), limits["min_cases"], len(results) >= limits["min_cases"])
    ]
    values = averages(results)
    for metric, limit in limits["metrics"].items():
        value = values.get(metric)
        rows.append(GateRow(suite, metric, value, limit, value is not None and value >= limit))
    return rows
