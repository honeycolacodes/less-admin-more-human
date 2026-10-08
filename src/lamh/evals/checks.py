"""Deterministic checks. Same input, same verdict, no model involved."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lamh.evals.cases import Check, EvalCase

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")

_WEEKDAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
# "May" alone is usually a verb, so months only count with a day number, except unambiguous full names.
_MONTHS_FULL = r"january|february|march|april|june|july|august|september|october|november|december"
_MONTHS_SHORT = r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_RELATIVE = r"tomorrow|next week|next month|end of (?:the )?(?:day|week|month)|eod|eow|cob"

_DATE_PATTERNS = (
    ("weekday", re.compile(rf"\b({_WEEKDAYS})\b", re.IGNORECASE)),
    ("month", re.compile(rf"\b({_MONTHS_FULL})\b", re.IGNORECASE)),
    ("month", re.compile(rf"\b({_MONTHS_SHORT})\.? \d{{1,2}}\b", re.IGNORECASE)),
    ("date", re.compile(r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b")),
    ("date", re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")),
    ("relative", re.compile(rf"\b({_RELATIVE})\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class CheckResult:
    check: str
    passed: bool
    detail: str = ""
    graded: bool = False


def word_count(text: str) -> int:
    """Count words, ignoring Markdown symbols like bullets and heading marks."""
    return len(_WORD.findall(text))


def max_words(output: str, limit: int) -> CheckResult:
    count = word_count(output)
    return CheckResult(f"at most {limit} words", count <= limit, f"{count} words")


def not_contains(output: str, patterns: list[str]) -> CheckResult:
    hits = [pattern for pattern in patterns if re.search(pattern, output)]
    label = "avoids " + ", ".join(f"/{p}/" for p in patterns)
    return CheckResult(label, not hits, f"found {', '.join(hits)}" if hits else "")


def contains_all(output: str, needles: list[str]) -> CheckResult:
    lowered = output.lower()
    missing = [needle for needle in needles if needle.lower() not in lowered]
    label = "includes " + ", ".join(f'"{n}"' for n in needles)
    return CheckResult(label, not missing, f"missing {', '.join(missing)}" if missing else "")


def date_mentions(text: str) -> set[str]:
    """Find every date-like mention, normalized so "Fri" style variants compare equal."""
    found: set[str] = set()
    for kind, pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).lower()
            if kind in ("weekday", "month"):
                value = value[:3]
            found.add(f"{kind}:{value}")
    return found


def no_new_dates(output: str, inputs: dict[str, str]) -> CheckResult:
    allowed = date_mentions("\n".join(inputs.values()))
    new = sorted(date_mentions(output) - allowed)
    return CheckResult(
        "no dates or deadlines that were not in the input",
        not new,
        f"added {', '.join(n.split(':', 1)[1] for n in new)}" if new else "",
    )


def run_rule(check: Check, output: str, case: EvalCase) -> CheckResult:
    if check.kind == "max_words":
        return max_words(output, check.arg)
    if check.kind == "not_contains":
        return not_contains(output, check.arg)
    if check.kind == "contains_all":
        return contains_all(output, check.arg)
    if check.kind == "no_new_dates":
        return no_new_dates(output, case.inputs)
    raise ValueError(f"'{check.kind}' is not a rule check")
