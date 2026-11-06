"""The graders and the gate are tested with bad answers planted on purpose.

The assistant here can't write anything new, so without these tests the grounding check would
never see a failure, and nobody would know whether it works.
"""

import json

import pytest

from deskbot.answerer import Answer
from deskbot.knowledge import Chunk
from deskbot.tools import sample_orders
from evals import graders, run_evals
from evals.gate import averages, check
from evals.suites import CaseResult

CHUNKS = {"R1": Chunk(id="R1", title="Refunds", text="Refunds take 6 days. Ask by phone.")}


def answered(text: str, citations: list[str]) -> Answer:
    return Answer(outcome="ANSWERED", text=text, citations=citations)


@pytest.mark.parametrize(
    ("retrieved", "relevant", "k", "expected"),
    [
        (["A", "B"], ["A"], 1, 1.0),
        (["B", "A"], ["A"], 1, 0.0),
        (["B", "A"], ["A"], 2, 1.0),
        (["A", "X"], ["A", "B"], 2, 0.5),
    ],
)
def test_tc701_recall_at_k(retrieved, relevant, k, expected):
    assert graders.recall_at_k(retrieved, relevant, k) == expected


@pytest.mark.parametrize(
    ("retrieved", "expected"),
    [(["A", "B"], 1.0), (["B", "A"], 0.5), (["B", "C"], 0.0), ([], 0.0)],
)
def test_tc702_reciprocal_rank(retrieved, expected):
    assert graders.reciprocal_rank(retrieved, ["A"]) == expected


def test_tc703_an_answer_taken_from_its_citation_is_grounded():
    assert graders.is_grounded(answered("Refunds take 6 days.", ["R1"]), CHUNKS)


@pytest.mark.parametrize(
    ("planted", "why"),
    [
        (answered("Refunds take 2 days.", ["R1"]), "a changed fact"),
        (answered("Refunds take 6 days. Refunds are free.", ["R1"]), "one invented sentence"),
        (answered("Refunds take 6 days.", []), "no citation"),
        (answered("Refunds take 6 days.", ["R9"]), "a citation that does not exist"),
    ],
    ids=["changed-fact", "invented-sentence", "no-citation", "made-up-citation"],
)
def test_tc704_a_planted_ungrounded_answer_is_caught(planted, why):
    assert not graders.is_grounded(planted, CHUNKS), why


def test_tc705_a_refusal_has_nothing_to_ground():
    assert graders.is_grounded(Answer(outcome="DECLINED", text="I can't help."), CHUNKS)


def test_tc706_facts_are_matched_without_regard_to_case():
    assert graders.contains_facts("Takes 4 WORKING days", ["4 working days"])
    assert not graders.contains_facts("Takes 5 working days", ["4 working days"])


def test_tc707_state_is_compared_field_by_field():
    orders = sample_orders()

    assert graders.state_matches({"O-1001": {"refunded": 0}}, orders)
    assert not graders.state_matches({"O-1001": {"refunded": 30}}, orders)


def results(*values: float) -> list[CaseResult]:
    return [CaseResult(f"TC-{index}", True, {"score": value}) for index, value in enumerate(values)]


def test_tc711_averages_use_only_the_cases_that_have_the_metric():
    both = [*results(1.0, 0.0), CaseResult("TC-9", True, {"other": 1.0})]

    assert averages(both) == {"score": 0.5, "other": 1.0}


def test_tc712_a_metric_at_its_limit_passes():
    rows = check("suite", results(1.0, 0.0), {"min_cases": 2, "metrics": {"score": 0.5}})

    assert all(row.passed for row in rows)


def test_tc713_a_metric_below_its_limit_fails():
    rows = check("suite", results(0.0, 0.0), {"min_cases": 2, "metrics": {"score": 0.5}})

    assert [row.metric for row in rows if not row.passed] == ["score"]


def test_tc714_too_few_cases_fail():
    rows = check("suite", results(1.0), {"min_cases": 2, "metrics": {"score": 0.5}})

    assert [row.metric for row in rows if not row.passed] == ["cases"]


def test_tc715_a_metric_nobody_measured_fails():
    rows = check("suite", results(1.0), {"min_cases": 1, "metrics": {"renamed": 0.5}})

    assert [row.metric for row in rows if not row.passed] == ["renamed"]


def test_tc721_the_full_run_passes_the_gate_and_writes_its_files(monkeypatch, tmp_path):
    # Given: the real cases and configs, with the reports in a temporary folder
    monkeypatch.setattr(run_evals, "REPORTS", tmp_path)

    # When
    exit_code = run_evals.main()

    # Then
    assert exit_code == 0
    assert "| rag | grounded | 1.000" in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_tc722_traces_hold_no_personal_data(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "REPORTS", tmp_path)

    run_evals.main()

    traces = (tmp_path / "traces.jsonl").read_text(encoding="utf-8")
    assert "@example.test" not in traces
    assert len(traces.splitlines()) == 61
    assert {json.loads(line)["suite"] for line in traces.splitlines()} == {
        "rag",
        "robustness",
        "security",
        "agent",
    }


def test_tc723_a_failing_gate_exits_with_1(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "REPORTS", tmp_path)
    real = run_evals.load_config

    def stricter(name: str) -> dict:
        config = real(name)
        if name == "quality_gate.toml":
            config["robustness"]["metrics"]["answer_correct"] = 0.99
        return config

    monkeypatch.setattr(run_evals, "load_config", stricter)

    assert run_evals.main() == 1
    assert "FAIL" in (tmp_path / "summary.md").read_text(encoding="utf-8")
