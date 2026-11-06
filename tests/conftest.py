"""Shared fixtures. Everything is built fresh and runs offline."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from deskbot.agent import Finish, Step, ToolCall
from deskbot.answerer import Answerer
from deskbot.knowledge import Chunk
from deskbot.tools import Toolbox
from evals.suites import build_answerer, load_cases

ROOT = Path(__file__).resolve().parents[1]


def cases(file: str) -> list[dict]:
    return load_cases(ROOT / "datasets" / file)


def case_id(case: dict) -> str:
    return case["id"]


@pytest.fixture(scope="session")
def settings() -> dict:
    with (ROOT / "configs/eval.toml").open("rb") as file:
        return tomllib.load(file)


@pytest.fixture(scope="session")
def assistant(settings) -> tuple[Answerer, dict[str, Chunk]]:
    return build_answerer(ROOT, settings)


@pytest.fixture
def answerer(assistant) -> Answerer:
    return assistant[0]


@pytest.fixture
def chunks(assistant) -> dict[str, Chunk]:
    return assistant[1]


@pytest.fixture
def toolbox() -> Toolbox:
    return Toolbox()


@dataclass
class ScriptedPlanner:
    """Plays a fixed list of actions, like a model that does what it wants. The last one repeats."""

    actions: list[ToolCall | Finish]

    def next_action(self, task: str, steps: list[Step]) -> ToolCall | Finish:
        return self.actions[min(len(steps), len(self.actions) - 1)]


@pytest.fixture
def scripted():
    return lambda *actions: ScriptedPlanner(list(actions))
