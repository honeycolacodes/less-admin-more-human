from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lamh import content
from lamh.evals.cases import CaseError, Check, load_cases, parse_cases


def _valid() -> dict[str, Any]:
    return {
        "prompt": "follow-up",
        "name": "basic",
        "inputs": {"notes": "Sam sends the brief Friday."},
        "checks": [{"max_words": 150}, {"rubric": "Keeps Sam's commitment."}],
    }


def test_real_cases_file_is_valid_and_covers_every_prompt(real_library: content.Library) -> None:
    cases = load_cases(library=real_library)
    assert {c.prompt_id for c in cases} == {p["id"] for p in real_library["prompts"]}
    assert len({c.id for c in cases}) == len(cases)
    assert all(c.checks for c in cases)


def test_parse_valid_case(real_library: content.Library) -> None:
    (case,) = parse_cases([_valid()], real_library)
    assert case.id == "follow-up/basic"
    assert case.checks == (Check("max_words", 150), Check("rubric", "Keeps Sam's commitment."))
    assert case.checks[1].is_rubric
    assert not case.checks[0].is_rubric


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"prompt": "nope"}, "no prompt with id 'nope'"),
        ({"inputs": {}}, "missing input 'notes'"),
        ({"inputs": {"notes": "x", "extra": "y"}}, "'extra' is not a field"),
        ({"inputs": "notes"}, "inputs must be a mapping"),
        ({"checks": []}, "needs at least one check"),
        ({"checks": [{"spell_check": True}]}, "unknown check 'spell_check'"),
        ({"checks": [{"max_words": -5}]}, "bad value for 'max_words'"),
        ({"checks": [{"max_words": True}]}, "bad value for 'max_words'"),
        ({"checks": [{"not_contains": "—"}]}, "bad value for 'not_contains'"),
        ({"checks": [{"no_new_dates": False}]}, "bad value for 'no_new_dates'"),
        ({"checks": [{"rubric": "  "}]}, "bad value for 'rubric'"),
        ({"checks": [{"max_words": 5, "rubric": "x"}]}, "exactly one key"),
    ],
)
def test_invalid_cases_are_reported(
    real_library: content.Library, change: dict[str, Any], message: str
) -> None:
    case = {**_valid(), **change}
    with pytest.raises(CaseError) as error:
        parse_cases([case], real_library)
    assert any(message in problem for problem in error.value.problems), error.value.problems


def test_structural_problems(real_library: content.Library) -> None:
    with pytest.raises(CaseError, match="non-empty list"):
        parse_cases({}, real_library)
    with pytest.raises(CaseError) as error:
        parse_cases(["not a mapping", {"prompt": "follow-up"}, _valid(), _valid()], real_library)
    problems = error.value.problems
    assert "case #1: must be a mapping" in problems
    assert "case #2: missing name, inputs, checks" in problems
    assert "follow-up/basic: duplicate case name" in problems


@pytest.mark.parametrize(
    ("check", "label"),
    [
        (Check("max_words", 150), "at most 150 words"),
        (Check("contains_all", ["Agreed"]), 'includes "Agreed"'),
        (Check("not_contains", ["—"]), "avoids /—/"),
        (Check("no_new_dates", True), "no dates or deadlines that were not in the input"),
        (Check("rubric", "Be kind."), "Be kind."),
    ],
)
def test_check_labels(check: Check, label: str) -> None:
    assert check.label == label


def test_load_cases_from_a_file(tmp_path: Path, real_library: content.Library) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "- prompt: follow-up\n  name: from-file\n  inputs:\n    notes: hi\n  checks:\n    - max_words: 10\n",
        encoding="utf-8",
    )
    assert load_cases(path, real_library)[0].id == "follow-up/from-file"
