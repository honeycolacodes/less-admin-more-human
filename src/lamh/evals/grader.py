"""Model-graded rubric checks: one yes-or-no criterion per grader call.

Grading one rule at a time keeps verdicts focused and makes a failure easy to
read: you see exactly which promise the prompt broke and why.
"""

from __future__ import annotations

import json
import re

from lamh.evals.checks import CheckResult
from lamh.evals.client import ModelClient

GRADER_MAX_TOKENS = 2000

GRADER_SYSTEM = """You are a strict, fair grader of AI assistant responses.
You judge one rule at a time. Judge only the rule you are given, not overall quality.
If the rule is clearly satisfied, pass it. If it is broken or only partly met, fail it.
Reply with only a JSON object and nothing else:
{"pass": true or false, "reason": "one short sentence explaining the verdict"}"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class VerdictError(ValueError):
    """The grader replied with something that is not a usable verdict."""


def grader_prompt(rule: str, prompt_text: str, output: str) -> str:
    return (
        f"<rule>\n{rule}\n</rule>\n\n"
        f"<prompt_given_to_assistant>\n{prompt_text}\n</prompt_given_to_assistant>\n\n"
        f"<assistant_response>\n{output}\n</assistant_response>\n\n"
        "Does the assistant response satisfy the rule? Reply with the JSON object only."
    )


def parse_verdict(text: str) -> tuple[bool, str]:
    """Pull {"pass": bool, "reason": str} out of the grader's reply, tolerating code fences."""
    match = _JSON_OBJECT.search(text)
    if not match:
        raise VerdictError(f"no JSON object in grader reply: {text[:120]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        raise VerdictError(f"grader reply is not valid JSON: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("pass"), bool):
        raise VerdictError(f"grader reply has no boolean 'pass': {match.group(0)[:120]!r}")
    return data["pass"], str(data.get("reason", "")).strip()


def grade(client: ModelClient, model: str, rule: str, prompt_text: str, output: str) -> CheckResult:
    reply = client.complete(
        grader_prompt(rule, prompt_text, output),
        model=model,
        max_tokens=GRADER_MAX_TOKENS,
        system=GRADER_SYSTEM,
    )
    try:
        passed, reason = parse_verdict(reply)
    except VerdictError as error:
        return CheckResult(rule, False, f"grader error: {error}", graded=True)
    return CheckResult(rule, passed, reason, graded=True)
