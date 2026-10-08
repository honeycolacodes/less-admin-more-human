"""Load the prompt library and render prompt templates.

data/prompts.json is the single source of truth. Every output (PDF, web tool,
Markdown, evals) goes through these functions, so they always agree. The web
tool has a JavaScript twin in site/render.js; tests/test_parity.py proves the
two produce identical text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "prompts.json"

#: A blank in a prompt template looks like {{job_post}}.
FIELD_PATTERN = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


class Field(TypedDict):
    key: str
    label: str
    hint: str


class OutputLine(TypedDict):
    lead: str
    text: str


class Example(TypedDict):
    input: str
    output_label: str
    output: str | list[OutputLine]


class Prompt(TypedDict):
    id: str
    number: str
    color: str
    audience: str
    short_audience: str
    title: str
    trigger: str
    cta: str
    use_when: str
    time: str
    have_ready: str
    prompt: str
    fields: list[Field]
    example: Example
    next_steps: list[str]
    bonus: NotRequired[bool]
    cover_label: NotRequired[str]
    step_title: NotRequired[str]
    blurb: NotRequired[str]
    tells: NotRequired[list[str]]
    _lint_ignore: NotRequired[list[str]]


class Color(TypedDict):
    tint: str
    deep: str
    label: str


class Author(TypedDict):
    name: str
    role: str
    linkedin: str


class Fix(TypedDict):
    problem: str
    color: str
    lead: NotRequired[str]
    text: NotRequired[str]
    reply: NotRequired[str]
    note: NotRequired[str]


class Library(TypedDict):
    """The parts of prompts.json the Python code reads. Templates see the rest too."""

    title: str
    author: Author
    colors: dict[str, Color]
    prompts: list[Prompt]
    fixes: list[Fix]


SegmentKind = Literal["text", "field"]
Segment = tuple[SegmentKind, str]


def load(path: Path = DATA_FILE) -> Library:
    """Read the prompt library from disk."""
    with path.open(encoding="utf-8") as handle:
        return cast(Library, json.load(handle))


def field_keys(template: str) -> list[str]:
    """Return the field keys a template uses, in order of first appearance."""
    return list(dict.fromkeys(FIELD_PATTERN.findall(template)))


def segments(prompt: Prompt, values: dict[str, str] | None = None) -> list[Segment]:
    """Split a prompt into ("text", str) and ("field", hint) pieces.

    Filled fields come back as plain text. Empty or whitespace-only ones come
    back as a field piece holding the hint, so each output can highlight them
    its own way (yellow in the PDF, a text box on the site).
    """
    values = values or {}
    hints = {field["key"]: field["hint"] for field in prompt["fields"]}
    template = prompt["prompt"]
    pieces: list[Segment] = []
    cursor = 0
    for match in FIELD_PATTERN.finditer(template):
        if match.start() > cursor:
            pieces.append(("text", template[cursor : match.start()]))
        key = match.group(1)
        value = values.get(key, "").strip()
        pieces.append(("text", value) if value else ("field", hints[key]))
        cursor = match.end()
    if cursor < len(template):
        pieces.append(("text", template[cursor:]))
    return pieces


def render_text(prompt: Prompt, values: dict[str, str] | None = None) -> str:
    """Render a prompt as plain text, with [hints] where values are missing."""
    return "".join(value if kind == "text" else f"[{value}]" for kind, value in segments(prompt, values))


def main_prompts(library: Library) -> list[Prompt]:
    return [p for p in library["prompts"] if not p.get("bonus")]


def bonus_prompts(library: Library) -> list[Prompt]:
    return [p for p in library["prompts"] if p.get("bonus")]


def get_prompt(library: Library, prompt_id: str) -> Prompt:
    for prompt in library["prompts"]:
        if prompt["id"] == prompt_id:
            return prompt
    raise KeyError(f"No prompt with id '{prompt_id}'")
