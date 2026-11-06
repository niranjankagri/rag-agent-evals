"""The same questions asked in other ways, conflicting sources and vague questions.

KNOWN_MISSES are real weaknesses of keyword retrieval, kept visible on purpose. strict=True means
a case that starts passing fails the run, so the list can't go stale when retrieval improves.
"""

import pytest

from conftest import case_id, cases
from evals import graders

KNOWN_MISSES = {
    "TC-201": "says nothing: no shared word with 'refund window'",
    "TC-202": "WRONG ANSWER: 'lost' pulls in the compensation section",
    "TC-203": "WRONG ANSWER: 'parcel' and 'driver' pull in the neighbour section",
    "TC-206": "says nothing: 'fast option' shares no word with 'express delivery'",
    "TC-207": "says nothing: 'move to another house' shares no word with 'change the address'",
    "TC-208": "says nothing: 'import tax' shares no word with 'customs duty'",
    "TC-210": "says nothing: the typo in 'refnud' leaves only one matching word",
}


def with_known_misses(case: dict):
    reason = KNOWN_MISSES.get(case["id"])
    marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
    return pytest.param(case, id=case_id(case), marks=marks)


@pytest.mark.parametrize("case", [with_known_misses(case) for case in cases("robustness_cases.jsonl")])
def test_a_reworded_question_keeps_its_answer(case, answerer):
    answer = answerer.answer(case["question"])

    assert answer.outcome == case["outcome"]
    assert graders.contains_facts(answer.text, case["must_contain"]), answer.text


def test_tc241_the_answer_comes_from_the_section_that_replaced_the_old_one(answerer):
    answer = answerer.answer("How long does refund money take to reach my payment method?")

    assert answer.citations == ["N1"]
    assert "6 working days" not in answer.text


def test_tc242_a_superseded_section_is_never_retrieved(answerer):
    answer = answerer.answer("Refund money reaches the original payment method in 6 working days")

    assert "R3" not in answer.retrieved
