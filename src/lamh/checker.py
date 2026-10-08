"""Check the prompt library for structural errors and AI-sounding copy.

Fails when:
  * a prompt is missing a required key, or ids and numbers repeat
  * a template uses a {{field}} that is not defined, or defines one it never uses
  * a prompt does not have exactly three next steps
  * copy contains long dashes or stock AI phrases

To show a tell on purpose (like the examples on the bonus page), list its path
in that prompt's "_lint_ignore", or wrap Markdown lines in
<!-- lint-ignore-start --> and <!-- lint-ignore-end -->.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lamh import content

REQUIRED_KEYS = (
    "id", "number", "color", "audience", "short_audience", "title", "trigger", "cta",
    "use_when", "time", "have_ready", "prompt", "fields", "example", "next_steps",
)  # fmt: skip

#: Phrases that make writing sound machine-made. Matched case-insensitively.
TELLS = (
    "—",  # long dash
    " -- ",
    "i'd love to",
    "i’d love to",
    "delve",
    "leverage",
    "elevate",
    "hope this finds you well",
    "fast-paced world",
    "game-changer",
    "game changer",
    "unlock",
    "seamless",
    "synerg",
    "tapestry",
    "in conclusion",
)

DOCS = ("README.md", "CONTRIBUTING.md")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def walk(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (path, text) for every string in a JSON structure, skipping "_private" keys."""
    if isinstance(node, dict):
        for key, value in node.items():
            if not key.startswith("_"):
                yield from walk(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


def find_tells(text: str) -> list[str]:
    lowered = text.lower()
    return [tell for tell in TELLS if tell in lowered]


def check_structure(library: content.Library) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_numbers: set[str] = set()
    for prompt in library["prompts"]:
        raw: dict[str, Any] = dict(prompt)
        name = raw.get("id", "<missing id>")
        errors += [f"{name}: missing '{key}'" for key in REQUIRED_KEYS if key not in raw]
        if name in seen_ids:
            errors.append(f"{name}: duplicate id")
        seen_ids.add(name)
        number = raw.get("number", "")
        if number in seen_numbers:
            errors.append(f"{name}: duplicate number {number}")
        seen_numbers.add(number)
        if raw.get("color") not in library["colors"]:
            errors.append(f"{name}: unknown color '{raw.get('color')}'")
        used = set(content.field_keys(raw.get("prompt", "")))
        defined = {f["key"] for f in raw.get("fields", [])}
        errors += [
            f"{name}: template uses {{{{{key}}}}} but no field defines it" for key in sorted(used - defined)
        ]
        errors += [f"{name}: field '{key}' is defined but never used" for key in sorted(defined - used)]
        if len(raw.get("next_steps", [])) != 3:
            errors.append(f"{name}: needs exactly 3 next steps")
    errors += [
        f"fix '{fix.get('problem')}': unknown color"
        for fix in library["fixes"]
        if fix.get("color") not in library["colors"]
    ]
    return errors


def _ignored_paths(library: content.Library) -> set[str]:
    ignored: set[str] = set()
    for index, prompt in enumerate(library["prompts"]):
        ignored.update(f"prompts[{index}].{rel}" for rel in prompt.get("_lint_ignore", []))
    return ignored


def _is_ignored(path: str, ignored: set[str]) -> bool:
    return any(path == skip or path.startswith((f"{skip}[", f"{skip}.")) for skip in ignored)


def check_copy(library: content.Library, docs_root: Path = content.ROOT) -> list[str]:
    errors: list[str] = []
    ignored = _ignored_paths(library)
    for path, text in walk(library):
        if not _is_ignored(path, ignored):
            errors += [f"data/prompts.json {path}: contains '{tell.strip()}'" for tell in find_tells(text)]

    for doc in DOCS:
        file = docs_root / doc
        if file.exists():
            errors += check_markdown(file.read_text(encoding="utf-8"), doc)
    return errors


def check_markdown(text: str, name: str) -> list[str]:
    """Find tells in Markdown, skipping code blocks and lint-ignore regions."""
    errors: list[str] = []
    skipping = in_code = False
    for number, line in enumerate(text.splitlines(), start=1):
        if "lint-ignore-start" in line:
            skipping = True
        elif "lint-ignore-end" in line:
            skipping = False
        elif line.strip().startswith("```"):
            in_code = not in_code
        elif not skipping and not in_code:
            errors += [f"{name}:{number}: contains '{tell.strip()}'" for tell in find_tells(line)]
    return errors


def run(library: content.Library, docs_root: Path = content.ROOT) -> Report:
    report = Report(errors=check_structure(library) + check_copy(library, docs_root))
    if not library["author"].get("linkedin"):
        report.warnings.append(
            "author.linkedin is empty, so the guide shows a [YOUR LINKEDIN URL] placeholder"
        )
    return report
