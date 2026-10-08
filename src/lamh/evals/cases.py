"""Load and validate eval cases from evals/cases.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lamh import content

CASES_FILE = content.ROOT / "evals" / "cases.yaml"
RULE_KINDS = ("max_words", "not_contains", "contains_all", "no_new_dates")
CHECK_KINDS = (*RULE_KINDS, "rubric")


class CaseError(ValueError):
    """Raised when cases.yaml is malformed. Lists every problem at once."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Invalid eval cases:\n  " + "\n  ".join(problems))


@dataclass(frozen=True)
class Check:
    kind: str
    arg: Any

    @property
    def is_rubric(self) -> bool:
        return self.kind == "rubric"

    @property
    def label(self) -> str:
        if self.kind == "rubric":
            return str(self.arg)
        if self.kind == "no_new_dates":
            return "no dates or deadlines that were not in the input"
        if self.kind == "max_words":
            return f"at most {self.arg} words"
        if self.kind == "contains_all":
            return "includes " + ", ".join(f'"{needle}"' for needle in self.arg)
        return "avoids " + ", ".join(f"/{pattern}/" for pattern in self.arg)


@dataclass(frozen=True)
class EvalCase:
    prompt_id: str
    name: str
    inputs: dict[str, str]
    checks: tuple[Check, ...]

    @property
    def id(self) -> str:
        return f"{self.prompt_id}/{self.name}"


def _validate_check(raw: Any, where: str) -> tuple[Check | None, list[str]]:
    if not isinstance(raw, dict) or len(raw) != 1:
        return None, [f"{where}: each check must be a mapping with exactly one key"]
    kind, arg = next(iter(raw.items()))
    if kind not in CHECK_KINDS:
        return None, [f"{where}: unknown check '{kind}' (expected one of {', '.join(CHECK_KINDS)})"]
    valid = {
        "max_words": isinstance(arg, int) and not isinstance(arg, bool) and arg > 0,
        "not_contains": isinstance(arg, list) and bool(arg) and all(isinstance(a, str) for a in arg),
        "contains_all": isinstance(arg, list) and bool(arg) and all(isinstance(a, str) for a in arg),
        "no_new_dates": arg is True,
        "rubric": isinstance(arg, str) and bool(arg.strip()),
    }[kind]
    if not valid:
        return None, [f"{where}: bad value for '{kind}': {arg!r}"]
    return Check(kind, arg), []


def parse_cases(raw: Any, library: content.Library) -> list[EvalCase]:
    """Turn parsed YAML into EvalCase objects, checking them against the prompt library."""
    if not isinstance(raw, list) or not raw:
        raise CaseError(["cases file must be a non-empty list"])
    prompts = {p["id"]: p for p in library["prompts"]}
    problems: list[str] = []
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"case #{index + 1}"
        if not isinstance(item, dict):
            problems.append(f"{where}: must be a mapping")
            continue
        missing = [key for key in ("prompt", "name", "inputs", "checks") if key not in item]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        where = f"{item['prompt']}/{item['name']}"
        prompt = prompts.get(item["prompt"])
        if prompt is None:
            problems.append(f"{where}: no prompt with id '{item['prompt']}'")
            continue
        if where in seen:
            problems.append(f"{where}: duplicate case name")
        seen.add(where)

        inputs = item["inputs"]
        expected = {field["key"] for field in prompt["fields"]}
        if not isinstance(inputs, dict):
            problems.append(f"{where}: inputs must be a mapping")
            continue
        problems += [f"{where}: missing input '{key}'" for key in sorted(expected - inputs.keys())]
        problems += [
            f"{where}: '{key}' is not a field of this prompt" for key in sorted(inputs.keys() - expected)
        ]

        if not isinstance(item["checks"], list) or not item["checks"]:
            problems.append(f"{where}: needs at least one check")
            continue
        checks: list[Check] = []
        for check_index, raw_check in enumerate(item["checks"]):
            check, errors = _validate_check(raw_check, f"{where} check #{check_index + 1}")
            problems += errors
            if check:
                checks.append(check)
        cases.append(
            EvalCase(
                prompt_id=item["prompt"],
                name=str(item["name"]),
                inputs={str(k): str(v) for k, v in inputs.items()},
                checks=tuple(checks),
            )
        )
    if problems:
        raise CaseError(problems)
    return cases


def load_cases(path: Path = CASES_FILE, library: content.Library | None = None) -> list[EvalCase]:
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return parse_cases(raw, library or content.load())
