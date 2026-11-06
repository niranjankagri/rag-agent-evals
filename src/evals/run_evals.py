"""Runs every suite, writes the report and traces, and exits with 1 if the gate fails.

python -m evals.run_evals
"""

import sys
import tomllib
from pathlib import Path

from evals.gate import GateRow, check
from evals.redact import redact_json
from evals.suites import SUITES, CaseResult

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"


def load_config(name: str) -> dict:
    with (ROOT / "configs" / name).open("rb") as file:
        return tomllib.load(file)


def _format(value: float | None) -> str:
    return "missing" if value is None else f"{value:.3f}"


def report(rows: list[GateRow], results: dict[str, list[CaseResult]]) -> str:
    lines = [
        "| Suite | Measure | Value | Limit | Result |",
        "|---|---|---:|---:|---|",
        *(
            f"| {row.suite} | {row.metric} | {_format(row.value)} | {row.limit} | "
            f"{'pass' if row.passed else 'FAIL'} |"
            for row in rows
        ),
    ]
    failed = [f"{suite}: {case.id}" for suite, cases in results.items() for case in cases if not case.passed]
    lines += ["", f"Failed cases: {', '.join(failed) if failed else 'none'}", ""]
    return "\n".join(lines)


def write_traces(folder: Path, results: dict[str, list[CaseResult]]) -> None:
    """One redacted line per case, so a failure can be studied after the run."""
    with (folder / "traces.jsonl").open("w", encoding="utf-8") as file:
        for suite, cases in results.items():
            for case in cases:
                record = {
                    "suite": suite,
                    "id": case.id,
                    "passed": case.passed,
                    "milliseconds": round(case.milliseconds, 2),
                    "trace": case.trace,
                }
                file.write(redact_json(record) + "\n")


def main() -> int:
    settings = load_config("eval.toml")
    limits = load_config("quality_gate.toml")

    results = {name: run(ROOT, settings) for name, run in SUITES.items()}
    rows = [row for name, cases in results.items() for row in check(name, cases, limits[name])]

    REPORTS.mkdir(exist_ok=True)
    text = report(rows, results)
    (REPORTS / "summary.md").write_text(text, encoding="utf-8")
    write_traces(REPORTS, results)
    print(text)
    return 0 if all(row.passed for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
