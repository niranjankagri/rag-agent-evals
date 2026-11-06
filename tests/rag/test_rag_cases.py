"""Every case in rag_cases.jsonl, checked one by one, so a failure names its case."""

import pytest

from conftest import case_id, cases
from evals import graders

ANSWERABLE = [case for case in cases("rag_cases.jsonl") if case["outcome"] == "ANSWERED"]
NOT_COVERED = [case for case in cases("rag_cases.jsonl") if case["outcome"] == "NOT_FOUND"]


@pytest.mark.parametrize("case", ANSWERABLE, ids=case_id)
def test_a_covered_question_finds_its_section_and_fact(case, answerer, chunks):
    # When
    answer = answerer.answer(case["question"])

    # Then
    assert answer.outcome == "ANSWERED"
    assert graders.recall_at_k(answer.retrieved, case["relevant"], 3) == 1
    assert graders.contains_facts(answer.text, case["must_contain"]), answer.text
    assert graders.is_grounded(answer, chunks)


@pytest.mark.parametrize("case", NOT_COVERED, ids=case_id)
def test_a_question_the_knowledge_base_cannot_answer_gets_no_answer(case, answerer):
    answer = answerer.answer(case["question"])

    assert answer.outcome == "NOT_FOUND"
    assert answer.text == ""
    assert answer.citations == []


def test_tc141_the_same_question_gives_the_same_answer(answerer):
    question = ANSWERABLE[0]["question"]

    assert answerer.answer(question) == answerer.answer(question)


def test_tc142_a_price_with_a_decimal_point_is_not_cut_in_half(answerer):
    answer = answerer.answer("How much does express delivery cost?")

    assert answer.text == "Express delivery costs 11.40 euros per parcel."
