"""Rule-based graders. Each takes what the system did and returns plain facts, never an opinion."""

from deskbot.answerer import Answer, split_sentences
from deskbot.knowledge import Chunk


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    """The share of the relevant sections found in the first k results."""
    found = set(retrieved[:k]) & set(relevant)
    return len(found) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: list[str]) -> float:
    """1 if the first result is relevant, 1/2 if the second is, and so on; 0 if none is."""
    for position, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in relevant:
            return 1 / position
    return 0.0


def contains_facts(text: str, facts: list[str]) -> bool:
    return all(fact.lower() in text.lower() for fact in facts)


def is_grounded(answer: Answer, chunks: dict[str, Chunk]) -> bool:
    """Every sentence must appear in a section the answer cites, and every citation must exist.

    Only an ANSWERED answer makes a claim. A refusal has nothing to ground.
    """
    if answer.outcome != "ANSWERED":
        return True
    if not answer.citations or any(cited not in chunks for cited in answer.citations):
        return False
    evidence = " ".join(chunks[cited].text for cited in answer.citations)
    return all(sentence in evidence for sentence in split_sentences(answer.text))


def state_matches(expected: dict, orders: dict) -> bool:
    """Checks the fields a case names, so it doesn't have to list the whole order."""
    return all(
        getattr(orders[order_id], name) == value
        for order_id, fields in expected.items()
        for name, value in fields.items()
    )
