from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from lamh import content


@pytest.fixture(scope="session")
def real_library() -> content.Library:
    return content.load()


@pytest.fixture
def library(real_library: content.Library) -> content.Library:
    """A fresh, mutable copy of the real prompt library for each test."""
    return copy.deepcopy(real_library)


@pytest.fixture
def prompt() -> content.Prompt:
    """A small, valid prompt to test rendering against."""
    return {
        "id": "demo",
        "number": "01",
        "color": "lilac",
        "audience": "For testers",
        "short_audience": "Testers",
        "title": "A demo prompt.",
        "trigger": "I need a demo.",
        "cta": "Try the demo",
        "use_when": "Testing.",
        "time": "1 min",
        "have_ready": "Nothing",
        "prompt": "Summarize {{notes}} for {{ audience }}.\nNOTES AGAIN: {{notes}}",
        "fields": [
            {"key": "notes", "label": "Notes", "hint": "paste notes"},
            {"key": "audience", "label": "Audience", "hint": "who reads it"},
        ],
        "example": {"input": "x", "output_label": "y", "output": "z"},
        "next_steps": ["one", "two", "three"],
    }


@pytest.fixture
def write_library(tmp_path: Path) -> Callable[[Any], Path]:
    def _write(data: Any) -> Path:
        path = tmp_path / "prompts.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return _write


class FakeClient:
    """A ModelClient that answers from a script instead of the network.

    `answer` produces the reply to a prompt being evaluated. `grade` produces the
    grader's reply for a rubric rule. Calls are recorded for assertions.
    """

    def __init__(
        self,
        answer: Callable[[str], str] | str = "A fine answer.",
        grade: Callable[[str], str] | str = '{"pass": true, "reason": "ok"}',
    ) -> None:
        self._answer = answer
        self._grade = grade
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def complete(self, prompt: str, *, model: str, max_tokens: int, system: str | None = None) -> str:
        with self._lock:
            self.calls.append({"prompt": prompt, "model": model, "system": system})
        if system:  # only the grader sends a system prompt
            rule = prompt.split("<rule>\n", 1)[1].split("\n</rule>", 1)[0]
            return self._grade(rule) if callable(self._grade) else self._grade
        return self._answer(prompt) if callable(self._answer) else self._answer


@pytest.fixture
def fake_client_class() -> type[FakeClient]:
    return FakeClient
