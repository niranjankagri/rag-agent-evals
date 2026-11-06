"""The four eval suites. Each runs its case file and returns one result per case."""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from deskbot.agent import Agent
from deskbot.answerer import Answer, Answerer
from deskbot.knowledge import Chunk, load_knowledge, usable_chunks
from deskbot.planner import RulePlanner
from deskbot.retriever import Retriever
from deskbot.tools import Toolbox
from evals import graders


@dataclass
class CaseResult:
    """How one case went. metrics holds the numbers that go into the suite's averages."""

    id: str
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    milliseconds: float = 0.0


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


def build_answerer(root: Path, settings: dict) -> tuple[Answerer, dict[str, Chunk]]:
    chunks = usable_chunks(load_knowledge(root / "datasets/knowledge"))
    answerer = Answerer(Retriever(chunks), settings["min_score"], settings["top_k"], settings["min_terms"])
    return answerer, {chunk.id: chunk for chunk in chunks}


def _timed(run, *args, **kwargs):
    start = time.perf_counter()
    result = run(*args, **kwargs)
    return result, (time.perf_counter() - start) * 1000


def _grade_answer(case: dict, answer: Answer, chunks: dict[str, Chunk], k: int) -> CaseResult:
    right_outcome = answer.outcome == case["outcome"]
    facts = graders.contains_facts(answer.text, case["must_contain"])
    grounded = graders.is_grounded(answer, chunks)
    correct = right_outcome and facts
    metrics = {
        "answer_correct": float(correct),
        # Saying "I don't know" is a miss; a confident wrong answer is much worse, so it's counted apart
        "no_wrong_answer": float(correct or answer.outcome == "NOT_FOUND"),
        "grounded": float(grounded),
    }
    if case["relevant"]:
        metrics["recall_at_k"] = graders.recall_at_k(answer.retrieved, case["relevant"], k)
        metrics["reciprocal_rank"] = graders.reciprocal_rank(answer.retrieved, case["relevant"])
    else:
        metrics["abstained"] = float(answer.outcome == "NOT_FOUND")
    return CaseResult(case["id"], correct and grounded, metrics, asdict(answer))


def run_rag(root: Path, settings: dict, file: str = "rag_cases.jsonl") -> list[CaseResult]:
    answerer, chunks = build_answerer(root, settings)
    results = []
    for case in load_cases(root / "datasets" / file):
        answer, took = _timed(answerer.answer, case["question"])
        result = _grade_answer(case, answer, chunks, settings["top_k"])
        result.milliseconds = took
        results.append(result)
    return results


def run_robustness(root: Path, settings: dict) -> list[CaseResult]:
    return run_rag(root, settings, "robustness_cases.jsonl")


def run_security(root: Path, settings: dict) -> list[CaseResult]:
    answerer, chunks = build_answerer(root, settings)
    results = []
    for case in load_cases(root / "datasets/security_cases.jsonl"):
        answer, took = _timed(answerer.answer, case["question"], role=case["role"])
        leaked = any(text.lower() in answer.text.lower() for text in case["must_not_contain"])
        passed = answer.outcome == case["outcome"] and not leaked
        metrics = {"safe": float(passed), "grounded": float(graders.is_grounded(answer, chunks))}
        results.append(CaseResult(case["id"], passed, metrics, asdict(answer), took))
    return results


def run_agent(root: Path, settings: dict) -> list[CaseResult]:
    results = []
    for case in load_cases(root / "datasets/agent_cases.jsonl"):
        toolbox = Toolbox()
        agent = Agent(RulePlanner(), toolbox, case["user"])
        result, took = _timed(agent.run, case["task"])
        checks = {
            "right_status": result.status == case["expected_status"],
            "right_tools": result.tools_called == case["expected_tools"],
            "right_state": graders.state_matches(case["expected_state"], toolbox.orders),
        }
        metrics = {name: float(value) for name, value in checks.items()}
        metrics["task_success"] = float(all(checks.values()))
        results.append(CaseResult(case["id"], all(checks.values()), metrics, asdict(result), took))
    return results


SUITES = {
    "rag": run_rag,
    "robustness": run_robustness,
    "security": run_security,
    "agent": run_agent,
}
