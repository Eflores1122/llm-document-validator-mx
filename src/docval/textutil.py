"""Normalization helpers for names, Mexican-shaped ids, and dates."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

_PARTICLES = frozenset({"DE", "DEL", "LA", "LAS", "LOS", "Y"})
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def name_tokens(value: str) -> list[str]:
    cleaned = strip_accents(value).upper().replace(",", " ")
    cleaned = re.sub(r"[^A-Z\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return [token for token in cleaned.split(" ") if token and token not in _PARTICLES]


def _compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) == 1 and right.startswith(left):
        return True
    if len(right) == 1 and left.startswith(right):
        return True
    if len(left) >= 5 and len(right) >= 5:
        return SequenceMatcher(None, left, right).ratio() >= 0.92
    return False


def _covers(source: list[str], target: list[str]) -> bool:
    used = [False] * len(target)
    for token in source:
        found = False
        for index, other in enumerate(target):
            if used[index]:
                continue
            if _compatible(token, other):
                used[index] = True
                found = True
                break
        if not found:
            return False
    return True


def names_match(left: str | None, right: str | None) -> bool:
    """True when two personal names are the same person under a conservative policy.

    Accents, punctuation, particle words, and surname-first order are ignored.
    A one-letter token may match a longer token as an initial. Extra surname
    tokens on only one side do not match.
    """
    if left is None or right is None:
        return False
    left_tokens = name_tokens(left)
    right_tokens = name_tokens(right)
    if not left_tokens or not right_tokens:
        return False
    return _covers(left_tokens, right_tokens) and _covers(right_tokens, left_tokens)


def normalize_id(value: str | None) -> str | None:
    """Uppercase an RFC or CURP and drop spaces and punctuation."""
    if value is None:
        return None
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return cleaned or None


def collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    match = _ISO_DATE.search(value)
    if match is None:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def find_labeled(text: str, labels: list[str]) -> str | None:
    """Return the value of the first matching `Label: value` line."""
    flags = re.IGNORECASE | re.MULTILINE
    for label in labels:
        pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", flags)
        match = pattern.search(text)
        if match is not None:
            return match.group(1).strip()
    return None
