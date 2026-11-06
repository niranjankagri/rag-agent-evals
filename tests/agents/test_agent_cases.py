"""The well-behaved planner: right tools, right status, right final state."""

import pytest

from conftest import case_id, cases
from deskbot.agent import Agent
from deskbot.planner import RulePlanner
from evals import graders


@pytest.mark.parametrize("case", cases("agent_cases.jsonl"), ids=case_id)
def test_a_task_ends_with_the_expected_tools_status_and_state(case, toolbox):
    # Given
    agent = Agent(RulePlanner(), toolbox, case["user"])

    # When
    result = agent.run(case["task"])

    # Then
    assert result.status == case["expected_status"]
    assert result.tools_called == case["expected_tools"]
    assert graders.state_matches(case["expected_state"], toolbox.orders)


def test_tc421_an_escalation_is_recorded_for_a_person_to_decide(toolbox):
    Agent(RulePlanner(), toolbox, "asha").run("Refund 80 euros for order O-1001")

    assert toolbox.escalations == [{"order_id": "O-1001", "reason": "Refund of 80"}]


def test_tc422_staff_can_refund_above_the_limit(toolbox):
    result = Agent(RulePlanner(), toolbox, "sam", role="staff").run("Refund 80 euros for order O-1001")

    assert result.status == "DONE"
    assert toolbox.orders["O-1001"].refunded == 80


def test_tc423_staff_can_see_any_customers_order(toolbox):
    result = Agent(RulePlanner(), toolbox, "sam", role="staff").run("Where is order O-1002?")

    assert result.status == "DONE"


def test_tc424_a_refund_above_the_amount_paid_fails_even_for_staff(toolbox):
    result = Agent(RulePlanner(), toolbox, "sam", role="staff").run("Refund 500 euros for order O-1003")

    assert result.status == "FAILED"
    assert toolbox.orders["O-1003"].refunded == 0
