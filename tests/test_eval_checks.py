from __future__ import annotations

import pytest

from lamh.evals import checks
from lamh.evals.cases import Check, EvalCase


def _case(**inputs: str) -> EvalCase:
    return EvalCase("follow-up", "t", inputs, ())


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("One two three.", 3),
        ("## Agreed\n- Sam sends the brief\n- **Open:** comp", 7),
        ("don't time-to-hire 41", 3),
        ("", 0),
    ],
)
def test_word_count_ignores_markdown(text: str, count: int) -> None:
    assert checks.word_count(text) == count


def test_max_words() -> None:
    assert checks.max_words("a b c", 3).passed
    result = checks.max_words("a b c d", 3)
    assert not result.passed
    assert result.detail == "4 words"


def test_not_contains_supports_regex_and_case_flags() -> None:
    assert checks.not_contains("Plain text.", ["—", "(?i)delve"]).passed
    result = checks.not_contains("Let us DELVE in — now", ["—", "(?i)delve"])
    assert not result.passed
    assert "(?i)delve" in result.detail


def test_contains_all_is_case_insensitive() -> None:
    assert checks.contains_all("AGREED: x\nstill open: y", ["Agreed", "Still open"]).passed
    result = checks.contains_all("Agreed only", ["Agreed", "Next steps"])
    assert not result.passed
    assert result.detail == "missing Next steps"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sam sends it Friday.", {"weekday:fri"}),
        ("Due friday, then FRIDAY again", {"weekday:fri"}),
        ("By Oct 12 or October", {"month:oct"}),
        ("We may ship.", set()),  # "may" the verb is not a month
        ("Ship May 3", {"month:may"}),
        ("on 10/12 and 2026-10-12", {"date:10/12", "date:2026-10-12"}),
        (
            "by EOD tomorrow, or end of the week",
            {"relative:eod", "relative:tomorrow", "relative:end of the week"},
        ),
        ("Thanks for the chat today.", set()),
    ],
)
def test_date_mentions(text: str, expected: set[str]) -> None:
    assert checks.date_mentions(text) == expected


def test_no_new_dates_allows_dates_from_the_input() -> None:
    case = _case(notes="Sam sends the role brief Friday.")
    assert checks.no_new_dates("Sam: brief by Friday.", case.inputs).passed
    result = checks.no_new_dates("Sam: brief by Friday. Lee joins next week.", case.inputs)
    assert not result.passed
    assert result.detail == "added next week"


def test_run_rule_dispatches_each_kind() -> None:
    case = _case(notes="Friday")
    output = "Agreed: Friday"
    assert checks.run_rule(Check("max_words", 5), output, case).passed
    assert checks.run_rule(Check("not_contains", ["—"]), output, case).passed
    assert checks.run_rule(Check("contains_all", ["agreed"]), output, case).passed
    assert checks.run_rule(Check("no_new_dates", True), output, case).passed
    with pytest.raises(ValueError, match="not a rule"):
        checks.run_rule(Check("rubric", "anything"), output, case)
