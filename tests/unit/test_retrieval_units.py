"""The building blocks, on small made-up data."""

import pytest

from deskbot.answerer import Answerer, split_sentences
from deskbot.knowledge import Chunk, parse_document, usable_chunks
from deskbot.retriever import Retriever, stem, tokenize


def chunk(chunk_id: str, text: str, **fields) -> Chunk:
    return Chunk(id=chunk_id, title="Title", text=text, **fields)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("refunds", "refund"),
        ("refunded", "refund"),
        ("refunding", "refund"),
        ("deliveries", "delivery"),
        ("damage", "damag"),
        ("damaged", "damag"),
        ("address", "address"),
        ("bus", "bus"),
    ],
)
def test_tc601_stemming_joins_forms_of_a_word(word, expected):
    assert stem(word) == expected


def test_tc602_tokens_are_lower_case_without_stopwords_and_with_synonyms():
    assert tokenize("Where is my SHIPMENT?") == ["parcel"]


def test_tc603_a_section_header_is_read():
    text = "access: staff\ntrust: official\n\n## S9 Some title\nSupersedes: S1\nLine one.\nLine two.\n"

    [parsed] = parse_document(text)

    assert (parsed.id, parsed.title, parsed.access, parsed.supersedes) == ("S9", "Some title", "staff", "S1")
    assert parsed.text == "Line one. Line two."


def test_tc604_a_replaced_section_is_dropped_and_its_replacement_kept():
    old = chunk("A", "old")
    new = chunk("B", "new", supersedes="A")

    assert usable_chunks([old, new]) == [new]


def test_tc605_the_better_match_ranks_first():
    retriever = Retriever([chunk("A", "bananas and apples"), chunk("B", "apples apples apples")])

    assert [hit.chunk.id for hit in retriever.search("apples")][0] == "B"


def test_tc606_a_rare_word_counts_for_more_than_a_common_one():
    retriever = Retriever(
        [chunk("A", "parcel parcel"), chunk("B", "parcel parcel"), chunk("C", "parcel customs")]
    )

    assert retriever.search("parcel customs")[0].chunk.id == "C"


def test_tc607_no_shared_word_gives_no_hits():
    assert Retriever([chunk("A", "apples")]).search("oranges") == []


def test_tc608_equal_scores_keep_a_fixed_order():
    retriever = Retriever([chunk("B", "apples"), chunk("A", "apples")])

    assert [hit.chunk.id for hit in retriever.search("apples")] == ["A", "B"]


def test_tc609_the_limit_is_respected():
    retriever = Retriever([chunk(str(number), "apples") for number in range(5)])

    assert len(retriever.search("apples", limit=2)) == 2


def test_tc610_a_decimal_point_does_not_end_a_sentence():
    assert split_sentences("It costs 11.40 euros. It is fast.") == ["It costs 11.40 euros.", "It is fast."]


def test_tc611_one_shared_word_is_not_enough_to_answer():
    retriever = Retriever([chunk("A", "tracking number and proof"), chunk("B", "other words here")])
    answerer = Answerer(retriever, min_score=0.1, top_k=3, min_terms=2)

    assert answerer.answer("telephone number").outcome == "NOT_FOUND"


def test_tc612_a_low_score_is_not_enough_to_answer():
    retriever = Retriever([chunk("A", "apples pears")])
    answerer = Answerer(retriever, min_score=100, top_k=3, min_terms=1)

    assert answerer.answer("apples pears").outcome == "NOT_FOUND"


def test_tc613_the_sentence_closest_to_the_question_is_chosen():
    retriever = Retriever([chunk("A", "Apples are red. Pears are green and sweet.")])
    answerer = Answerer(retriever, min_score=0.0, top_k=3, min_terms=1)

    assert answerer.answer("green pears").text == "Pears are green and sweet."
