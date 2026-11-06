"""BM25 keyword retrieval, written out in full so every score can be explained."""

import math
import re
from collections import Counter
from dataclasses import dataclass

from deskbot.knowledge import Chunk

K1 = 1.5  # How quickly repeats of a word stop adding to the score
B = 0.75  # How much a long section is penalised

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "the",
        "then",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    ]
)

# Keyword search has no idea that two words mean the same, so the known cases are listed.
# A paraphrase outside this list is a real miss, and the robustness suite shows how many there are.
SYNONYMS = {
    "shipment": "parcel",
    "package": "parcel",
    "courier": "driver",
    "missing": "lost",
    "vanished": "lost",
    "broken": "damaged",
    "reimbursed": "compensated",
    "repaid": "refunded",
}


def stem(word: str) -> str:
    """A very small stemmer: "refunds", "refunded" and "refunding" all become "refund"."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for ending in ("ing", "ed", "es", "s", "e"):
        # The length check keeps short words such as "bus" and "red" whole
        if word.endswith(ending) and not word.endswith("ss") and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


def tokenize(text: str) -> list[str]:
    """Lower-case words without stopwords, with synonyms replaced and plurals reduced."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(SYNONYMS.get(word, word)) for word in words if word not in STOPWORDS]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    matched_terms: int  # How many different question words this section contains


class Retriever:
    """Searches the given chunks. The access rule is applied here, before any scoring."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        # The title says what a section is about, so its words count double
        self._terms = [Counter(tokenize(f"{chunk.title} {chunk.title} {chunk.text}")) for chunk in chunks]
        self._lengths = [sum(terms.values()) for terms in self._terms]
        self._average_length = sum(self._lengths) / len(chunks)
        self._document_counts = Counter(term for terms in self._terms for term in terms)

    def _idf(self, term: str) -> float:
        # Rare words count for more; the +1 keeps the value above zero for very common words
        count = self._document_counts[term]
        return math.log(1 + (len(self._chunks) - count + 0.5) / (count + 0.5))

    def _score(self, query_terms: list[str], index: int) -> float:
        terms = self._terms[index]
        length_factor = 1 - B + B * self._lengths[index] / self._average_length
        score = 0.0
        for term in query_terms:
            frequency = terms[term]
            score += self._idf(term) * frequency * (K1 + 1) / (frequency + K1 * length_factor)
        return score

    def search(self, query: str, role: str = "customer", limit: int = 3) -> list[Hit]:
        """The best matching chunks this role may see, best first. No match gives an empty list."""
        query_terms = tokenize(query)
        hits = [
            Hit(chunk, self._score(query_terms, index), len(set(query_terms) & set(self._terms[index])))
            for index, chunk in enumerate(self._chunks)
            if chunk.access == "public" or role == "staff"
        ]
        # The ID breaks ties, so the order never depends on chance
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.id))
        return [hit for hit in hits if hit.score > 0][:limit]
