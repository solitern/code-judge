"""Output comparison for judge runs.

Default rules:
- compare non-whitespace tokens in order
- ignore differences in spaces, tabs, and line endings between tokens
- keep token contents and letter case significant
"""
from __future__ import annotations


def normalize_output(text: str | bytes) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    # Python's split() treats spaces, tabs and all common line endings as
    # separators, collapses repeated whitespace, and drops leading/trailing
    # whitespace. Joining makes the normalized value deterministic while
    # preserving every token exactly.
    return " ".join(text.split())


def compare_output(actual: str | bytes, expected: str | bytes) -> bool:
    return normalize_output(actual) == normalize_output(expected)
