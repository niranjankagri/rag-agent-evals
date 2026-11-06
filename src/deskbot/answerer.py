"""Turns retrieved sections into an answer, with citations, or says it has none.

The answer is extractive: it repeats sentences from the sections and writes nothing new. So it
behaves the same on every run. An LLM could replace it behind the same Answer type, and the
graders in evals/ wouldn't change.
"""

import re
from dataclasses import dataclass, field

from deskbot.retriever import Hit, Retriever, tokenize

# Requests that must never reach retrieval, whatever the knowledge base contains
DECLINE = re.compile(
    r"ignore (all |any )?(previous|prior)|forget your|you are now|system prompt|pretend you|"
    r"another customer|other customers?|customer on order",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Answer:
    outcome: str  # ANSWERED, NOT_FOUND or DECLINED
    text: str = ""
    citations: list[str] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)


def split_sentences(text: str) -> list[str]:
    # A full stop only ends a sentence before a space, so "11.40 euros" stays whole
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _overlap(question_terms: set[str], sentence: str) -> int:
    return len(question_terms & set(tokenize(sentence)))


class Answerer:
    def __init__(self, retriever: Retriever, min_score: float, top_k: int, min_terms: int = 2) -> None:
        self._retriever = retriever
        self._min_score = min_score
        self._top_k = top_k
        self._min_terms = min_terms

    def answer(self, question: str, role: str = "customer") -> Answer:
        if DECLINE.search(question):
            return Answer(outcome="DECLINED", text="I can't help with that.")

        hits = self._retriever.search(question, role=role, limit=self._top_k)
        retrieved = [hit.chunk.id for hit in hits]
        # A weak match means the knowledge base doesn't cover this: saying so beats guessing. One
        # shared word is weak however rare it is: "number" doesn't make a phone question about claims
        if not hits or hits[0].score < self._min_score or hits[0].matched_terms < self._min_terms:
            return Answer(outcome="NOT_FOUND", retrieved=retrieved)

        return self._from_best_section(question, hits[0], retrieved)

    def _from_best_section(self, question: str, best: Hit, retrieved: list[str]) -> Answer:
        terms = set(tokenize(question))
        sentences = split_sentences(best.chunk.text)
        # max() keeps the first of equals, so the opening sentence of a section wins a tie
        sentence = max(sentences, key=lambda candidate: _overlap(terms, candidate))
        return Answer(outcome="ANSWERED", text=sentence, citations=[best.chunk.id], retrieved=retrieved)
