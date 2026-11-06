"""Loads the knowledge base and decides which sections may be used at all."""

import re
from dataclasses import dataclass
from pathlib import Path

# Text that talks to the assistant instead of informing the reader. A knowledge base can be
# edited by more people than the code, so this is checked when a document is loaded.
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|disregard your|you are now|system prompt",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Chunk:
    """One section of a document: the unit that is retrieved and cited."""

    id: str
    title: str
    text: str
    access: str = "public"
    trust: str = "official"
    supersedes: str | None = None


def parse_document(text: str) -> list[Chunk]:
    """Reads the header lines of a document, then one chunk per "## ID Title" section."""
    header, *sections = re.split(r"^## ", text, flags=re.MULTILINE)
    meta = dict(line.split(": ", 1) for line in header.strip().splitlines())
    return [_parse_section(section, meta) for section in sections]


def _parse_section(section: str, meta: dict[str, str]) -> Chunk:
    heading, *lines = section.strip().splitlines()
    chunk_id, title = heading.split(" ", 1)
    supersedes = None
    if lines and lines[0].startswith("Supersedes: "):
        supersedes = lines.pop(0).removeprefix("Supersedes: ")
    return Chunk(
        id=chunk_id,
        title=title,
        text=" ".join(lines).strip(),
        access=meta.get("access", "public"),
        trust=meta.get("trust", "official"),
        supersedes=supersedes,
    )


def load_knowledge(folder: Path) -> list[Chunk]:
    """Every section of every document, in file name order so a run is repeatable."""
    chunks: list[Chunk] = []
    for path in sorted(folder.glob("*.md")):
        chunks.extend(parse_document(path.read_text(encoding="utf-8")))
    return chunks


def is_quarantined(chunk: Chunk) -> bool:
    """True for text that tries to instruct the assistant."""
    return INJECTION.search(chunk.text) is not None


def usable_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Drops sections replaced by a newer one, and sections in quarantine."""
    replaced = {chunk.supersedes for chunk in chunks if chunk.supersedes}
    return [chunk for chunk in chunks if chunk.id not in replaced and not is_quarantined(chunk)]
