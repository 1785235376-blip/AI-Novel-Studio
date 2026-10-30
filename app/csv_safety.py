"""Spreadsheet formula-injection neutralisation shared by CSV exports.

CSV quoting keeps commas and quotes inside one cell, but it does not stop a
spreadsheet application from evaluating a cell whose visible text begins with a
formula sigil. Several product exports carry author- or configuration-controlled
text, so every CSV writer uses the one policy declared here. It mirrors the rule
already applied by the Creative Director/Storyboard sheets, keeping exports
byte-identical for ordinary text and readable for neutralised cells.
"""
from __future__ import annotations

from typing import Any


FORMULA_SIGILS = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
_LEADING_INVISIBLE = "\ufeff\u200b\u200c\u200d\u2060"


def neutralize_formula(text: str) -> str:
    """Prefix one apostrophe when a spreadsheet would treat ``text`` as a formula.

    Leading whitespace and zero-width characters are skipped when deciding, but
    the original text is preserved byte for byte after the apostrophe so the
    reader still sees exactly what the author wrote.
    """
    index = 0
    while index < len(text) and (text[index].isspace() or text[index] in _LEADING_INVISIBLE):
        index += 1
    if text and (text[0] in "\t\r\n" or text[index:].startswith(FORMULA_SIGILS)):
        return "'" + text
    return text


def csv_safe_cell(value: Any) -> str:
    """Return one CSV cell that spreadsheets read as text, never as a formula."""
    text = "" if value is None else str(value)
    return neutralize_formula(text)
