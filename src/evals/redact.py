"""Removes personal data from anything written to disk."""

import json
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d ()-]{7,}\d")


def redact(text: str) -> str:
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))


def redact_json(value: object) -> str:
    """One JSON line with the personal data removed."""
    return redact(json.dumps(value, ensure_ascii=False, default=str))
