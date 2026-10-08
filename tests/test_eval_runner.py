from __future__ import annotations

import pytest

from lamh import content
from lamh.evals import grader, runner
from lamh.evals.cases import Check, EvalCase

GOOD_FOLLOW_UP = (
    "Agreed\n- Sam sends the brief Friday\n\nStill open\n- Comp\n\nNext steps\n- Lee might join (to confirm)"
)


def _case(name: str = "basic", *checks: Check) -> EvalCase:
    checks = checks or (Check("contains_all", ["Agreed"]), Check("rubric", "Keeps Sam's commitment."))
    return EvalCase("follow-up", name, {"notes": "Sam sends the brief Friday."}, checks)


def test_a_passing_case(real_library: content.Library, fake_client_class) -> None:
    client = fake_client_class(answer=GOOD_FOLLOW_UP)
    report = runner.run([_case()], real_library, client, model="m", grader_model="g", workers=1)
    (result,) = report.results
    assert result.passed
    assert report.pass_rate == 1.0
    assert "Sam sends the brief Friday." in result.prompt_text  # inputs were filled into the prompt
    generation, grading = client.calls
    assert generation["model"] == "m"
    assert generation["system"] is None
    assert grading["model"] == "g"
    assert grading["system"] == grader.GRADER_SYSTEM
    assert result.checks[1].graded
    assert not result.checks[0].graded


def test_failing_rule_and_rubric_are_reported(real_library: content.Library, fake_client_class) -> None:
    client = fake_client_class(answer="Nothing useful.", grade='{"pass": false, "reason": "Sam is missing."}')
    report = runner.run([_case()], real_library, client)
    (result,) = report.results
    assert not result.passed
    assert [c.passed for c in result.checks] == [False, False]
    assert result.checks[1].detail == "Sam is missing."
    assert report.pass_rate == 0.0
    assert report.cases_passed == 0


def test_api_errors_fail_the_case_not_the_run(real_library: content.Library, fake_client_class) -> None:
    def flaky(prompt: str) -> str:
        if "boom" in prompt:
            raise ConnectionError("network down")
        return GOOD_FOLLOW_UP

    ok = _case("ok")
    bad = EvalCase("follow-up", "bad", {"notes": "boom"}, (Check("max_words", 100),))
    report = runner.run([ok, bad], real_library, fake_client_class(answer=flaky), workers=2)
    assert [r.case.name for r in report.results] == ["ok", "bad"]  # order is kept despite threads
    assert report.results[0].passed
    assert report.results[1].error == "ConnectionError: network down"
    assert report.checks_passed == 2
    assert report.checks_total == 3


@pytest.mark.parametrize(
    ("reply", "verdict"),
    [
        ('{"pass": true, "reason": "Clear."}', (True, "Clear.")),
        ('```json\n{"pass": false, "reason": "Adds a date."}\n```', (False, "Adds a date.")),
        ('Sure! {"pass": true}', (True, "")),
    ],
)
def test_parse_verdict(reply: str, verdict: tuple[bool, str]) -> None:
    assert grader.parse_verdict(reply) == verdict


@pytest.mark.parametrize("reply", ["yes", '{"pass": "yes"}', "{not json}", "[]"])
def test_unusable_verdicts_fail_the_check(
    real_library: content.Library, fake_client_class, reply: str
) -> None:
    with pytest.raises(grader.VerdictError):
        grader.parse_verdict(reply)
    result = grader.grade(fake_client_class(grade=reply), "g", "Some rule.", "prompt", "output")
    assert not result.passed
    assert result.detail.startswith("grader error:")


def test_grader_prompt_contains_rule_prompt_and_output() -> None:
    text = grader.grader_prompt("No dates.", "THE PROMPT", "THE ANSWER")
    assert "<rule>\nNo dates.\n</rule>" in text
    assert "THE PROMPT" in text
    assert "THE ANSWER" in text


def test_reports_render_all_formats(real_library: content.Library, fake_client_class) -> None:
    def grade(rule: str) -> str:
        return (
            '{"pass": false, "reason": "nope"}' if "commitment" in rule else '{"pass": true, "reason": "ok"}'
        )

    report = runner.run(
        [_case("one"), _case("two")], real_library, fake_client_class(answer=GOOD_FOLLOW_UP, grade=grade)
    )
    data = report.to_dict()
    assert data["checks"] == {"passed": 2, "total": 4}
    assert data["cases"] == {"passed": 0, "total": 2}
    assert data["results"][0]["checks"][1] == {
        "check": "Keeps Sam's commitment.",
        "passed": False,
        "detail": "nope",
        "graded": True,
    }

    console = report.to_console()
    assert "FAIL  follow-up/one" in console
    assert "x Keeps Sam's commitment.  (nope)" in console
    assert "Checks: 2/4 passed (50%)" in console

    md = report.to_markdown()
    assert md.startswith("## Prompt evals")
    assert "**50%**" in md
    assert "<details><summary><code>follow-up/one</code></summary>" in md
    assert GOOD_FOLLOW_UP in md


def test_error_shows_in_reports(real_library: content.Library, fake_client_class) -> None:
    def boom(prompt: str) -> str:
        raise TimeoutError("slow")

    report = runner.run([_case()], real_library, fake_client_class(answer=boom))
    assert "error: TimeoutError: slow" in report.to_console()
    assert "**error:** TimeoutError: slow" in report.to_markdown()


def test_empty_report() -> None:
    report = runner.EvalReport("m", "g", [])
    assert report.pass_rate == 0.0
    assert "Cases:  0/0 passed" in report.to_console()


def test_dry_run_shows_prompts_checks_and_call_count(real_library: content.Library) -> None:
    text = runner.dry_run([_case()], real_library)
    assert "=== follow-up/basic ===" in text
    assert "NOTES: Sam sends the brief Friday." in text
    assert '[rule] includes "Agreed"' in text
    assert "[rubric] Keeps Sam's commitment." in text
    assert text.endswith("1 cases · 2 checks · 2 model calls when run for real")
