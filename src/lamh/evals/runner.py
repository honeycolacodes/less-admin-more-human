"""Run eval cases against a model and report the results."""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lamh import content
from lamh.evals.cases import EvalCase
from lamh.evals.checks import CheckResult, run_rule
from lamh.evals.client import ModelClient
from lamh.evals.grader import grade

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_GRADER = "claude-sonnet-5-5"
GENERATION_MAX_TOKENS = 8000


@dataclass
class CaseResult:
    case: EvalCase
    prompt_text: str
    output: str = ""
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(check.passed for check in self.checks)

    @property
    def score(self) -> str:
        """Checks passed out of checks planned, e.g. "4/5". Checks skipped by an error count as failed."""
        return f"{sum(c.passed for c in self.checks)}/{len(self.case.checks)}"


@dataclass
class EvalReport:
    model: str
    grader_model: str
    results: list[CaseResult]
    finished_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    @property
    def checks_total(self) -> int:
        return sum(len(r.case.checks) for r in self.results)

    @property
    def checks_passed(self) -> int:
        return sum(1 for r in self.results for c in r.checks if c.passed)

    @property
    def cases_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def pass_rate(self) -> float:
        """Share of all checks that passed. A case that errored counts every check as failed."""
        return self.checks_passed / self.checks_total if self.checks_total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "grader_model": self.grader_model,
            "finished_at": self.finished_at,
            "pass_rate": round(self.pass_rate, 4),
            "checks": {"passed": self.checks_passed, "total": self.checks_total},
            "cases": {"passed": self.cases_passed, "total": len(self.results)},
            "results": [
                {
                    "case": r.case.id,
                    "passed": r.passed,
                    "error": r.error,
                    "output": r.output,
                    "checks": [
                        {"check": c.check, "passed": c.passed, "detail": c.detail, "graded": c.graded}
                        for c in r.checks
                    ],
                }
                for r in self.results
            ],
        }

    def to_console(self) -> str:
        lines = []
        for r in self.results:
            lines.append(f"{'PASS' if r.passed else 'FAIL'}  {r.case.id:<42} {r.score}")
            if r.error:
                lines.append(f"      error: {r.error}")
            lines += [
                f"      x {c.check}" + (f"  ({c.detail})" if c.detail else "")
                for c in r.checks
                if not c.passed
            ]
        lines += [
            "",
            f"Cases:  {self.cases_passed}/{len(self.results)} passed",
            f"Checks: {self.checks_passed}/{self.checks_total} passed ({self.pass_rate:.0%})",
            f"Model:  {self.model}  ·  Grader: {self.grader_model}",
        ]
        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = [
            "## Prompt evals",
            "",
            f"**{self.pass_rate:.0%}** of checks passed ({self.checks_passed}/{self.checks_total}) · "
            f"**{self.cases_passed}/{len(self.results)}** cases fully passed",
            "",
            f"Model `{self.model}` · grader `{self.grader_model}` · {self.finished_at}",
            "",
            "| Case | Result | Checks |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| `{r.case.id}` | {'✅ pass' if r.passed else '❌ fail'} | {r.score} |" for r in self.results
        ]
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines += ["", "### Failures", ""]
            for r in failures:
                lines += [f"<details><summary><code>{r.case.id}</code></summary>", ""]
                if r.error:
                    lines.append(f"- **error:** {r.error}")
                lines += [f"- **{c.check}**: {c.detail or 'failed'}" for c in r.checks if not c.passed]
                if r.output:
                    lines += ["", "```text", r.output, "```"]
                lines += ["", "</details>", ""]
        return "\n".join(lines) + "\n"


def run_case(
    case: EvalCase, library: content.Library, client: ModelClient, *, model: str, grader_model: str
) -> CaseResult:
    prompt = content.get_prompt(library, case.prompt_id)
    result = CaseResult(case, content.render_text(prompt, case.inputs))
    try:
        result.output = client.complete(result.prompt_text, model=model, max_tokens=GENERATION_MAX_TOKENS)
        for check in case.checks:
            if check.is_rubric:
                result.checks.append(
                    grade(client, grader_model, check.arg, result.prompt_text, result.output)
                )
            else:
                result.checks.append(run_rule(check, result.output, case))
    except Exception as error:  # one failing API call should not sink the whole run
        result.error = f"{type(error).__name__}: {error}"
    return result


def run(
    cases: Sequence[EvalCase],
    library: content.Library,
    client: ModelClient,
    *,
    model: str = DEFAULT_MODEL,
    grader_model: str = DEFAULT_GRADER,
    workers: int = 4,
) -> EvalReport:
    """Run every case, in parallel, keeping results in case order."""
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(
            pool.map(lambda c: run_case(c, library, client, model=model, grader_model=grader_model), cases)
        )
    return EvalReport(model, grader_model, results)


def dry_run(cases: Sequence[EvalCase], library: content.Library) -> str:
    """Show what would be sent and checked, without calling a model."""
    blocks = []
    for case in cases:
        prompt = content.get_prompt(library, case.prompt_id)
        checks = "\n".join(f"  [{'rubric' if c.is_rubric else 'rule'}] {c.label}" for c in case.checks)
        blocks.append(f"=== {case.id} ===\n{content.render_text(prompt, case.inputs)}\n\nChecks:\n{checks}")
    rubric = sum(c.is_rubric for case in cases for c in case.checks)
    blocks.append(
        f"{len(cases)} cases · {sum(len(c.checks) for c in cases)} checks · "
        f"{len(cases) + rubric} model calls when run for real"
    )
    return "\n\n".join(blocks)
