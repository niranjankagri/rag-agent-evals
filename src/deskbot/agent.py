"""The agent loop and its guardrails.

A planner decides what to do next. In a real product that is a language model, which can ask for
anything. So every rule lives here, outside the planner: a bad plan is stopped by this code, not
by asking the planner to behave. The tests prove that with a planner that misbehaves on purpose.
"""

from dataclasses import dataclass, field
from typing import Protocol

from deskbot.tools import Toolbox, ToolError, ToolTimeout

MAX_STEPS = 6
REFUND_LIMIT = 50  # The same limit as knowledge section R4


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: dict


@dataclass(frozen=True)
class Finish:
    status: str  # DONE, ESCALATED, FAILED or NOT_UNDERSTOOD
    message: str = ""


@dataclass(frozen=True)
class Step:
    """What happened to one tool call. outcome: ok, error or blocked."""

    tool: str
    args: dict
    outcome: str
    result: dict | str


class Planner(Protocol):
    def next_action(self, task: str, steps: list[Step]) -> ToolCall | Finish: ...


@dataclass
class AgentResult:
    status: str
    message: str = ""
    steps: list[Step] = field(default_factory=list)

    @property
    def tools_called(self) -> list[str]:
        return [step.tool for step in self.steps]


class Agent:
    def __init__(self, planner: Planner, toolbox: Toolbox, user: str, role: str = "customer") -> None:
        self._planner = planner
        self._toolbox = toolbox
        self._specs = toolbox.specs()
        self._user = user
        self._role = role

    def run(self, task: str) -> AgentResult:
        steps: list[Step] = []
        for _ in range(MAX_STEPS):
            action = self._planner.next_action(task, steps)
            if isinstance(action, Finish):
                return AgentResult(action.status, action.message, steps)

            # The same call twice can never give new information, so the plan is stuck
            if any(step.tool == action.tool and step.args == action.args for step in steps):
                return AgentResult("STOPPED_LOOP", f"Repeated {action.tool}.", steps)

            step = self._execute(action)
            steps.append(step)
            # A permission failure ends the task: trying other things after it is how data leaks
            if step.outcome == "blocked" and step.result != "needs approval":
                return AgentResult("BLOCKED", str(step.result), steps)

        return AgentResult("STOPPED_LIMIT", f"Stopped after {MAX_STEPS} steps.", steps)

    def _execute(self, call: ToolCall) -> Step:
        problem = self._blocked_reason(call)
        if problem:
            return Step(call.tool, call.args, "blocked", problem)

        spec = self._specs[call.tool]
        try:
            return Step(call.tool, call.args, "ok", self._run_with_retry(spec, call))
        except ToolError as error:
            return Step(call.tool, call.args, "error", str(error))
        except ToolTimeout:
            return Step(call.tool, call.args, "error", "The tool did not answer.")

    def _run_with_retry(self, spec, call: ToolCall) -> dict:
        try:
            return spec.run(**call.args)
        except ToolTimeout:
            # Repeating a change could do it twice, because a timeout doesn't say it failed
            if spec.changes_state:
                raise
            return spec.run(**call.args)

    def _blocked_reason(self, call: ToolCall) -> str | None:
        """Why this call must not run, or None. The order of the checks matters."""
        spec = self._specs.get(call.tool)
        if spec is None:
            return f"Unknown tool {call.tool}."

        if set(call.args) != set(spec.params):
            return f"Wrong arguments for {call.tool}."
        for name, expected in spec.params.items():
            # bool is a kind of int in Python, and True must not pass as an amount
            value = call.args[name]
            if not isinstance(value, expected) or isinstance(value, bool):
                return f"Argument {name} of {call.tool} has the wrong type."

        return self._ownership_problem(call) or self._refund_problem(call)

    def _ownership_problem(self, call: ToolCall) -> str | None:
        order = self._toolbox.orders.get(call.args["order_id"])
        # An unknown order is left to the tool, which answers with a normal error
        if order and self._role != "staff" and order.customer != self._user:
            return "This order belongs to another customer."
        return None

    def _refund_problem(self, call: ToolCall) -> str | None:
        if call.tool != "issue_refund":
            return None
        amount = call.args["amount"]
        if amount <= 0:
            return "A refund must be a positive amount."
        order = self._toolbox.orders.get(call.args["order_id"])
        already_refunded = order.refunded if order else 0
        # The limit is per order, or several small refunds could get round it
        if already_refunded + amount > REFUND_LIMIT and self._role != "staff":
            return "needs approval"
        return None
