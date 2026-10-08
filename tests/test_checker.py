from __future__ import annotations

from pathlib import Path

import pytest

from lamh import checker, content


def test_real_library_passes(real_library: content.Library) -> None:
    report = checker.run(real_library)
    assert report.ok, report.errors


@pytest.mark.parametrize(
    "bad_copy",
    [
        "Hit send — today",
        "I'd love to help",
        "I’d love to help",
        "Let's delve in",
        "Leverage your network",
        "Elevate your hiring",
        "I hope this finds you well",
        "A seamless process",
    ],
)
def test_tells_in_copy_are_caught(library: content.Library, bad_copy: str) -> None:
    library["prompts"][0]["use_when"] = bad_copy
    errors = checker.check_copy(library, docs_root=Path("/nonexistent"))
    assert any("prompts[0].use_when" in e for e in errors)


def test_lint_ignore_allows_deliberate_examples(library: content.Library) -> None:
    strip = content.get_prompt(library, "strip-ai-tells")
    assert any("—" in tell for tell in strip["tells"])  # the bonus page shows a long dash on purpose
    assert checker.check_copy(library, docs_root=Path("/nonexistent")) == []
    del strip["_lint_ignore"]
    assert checker.check_copy(library, docs_root=Path("/nonexistent"))


def test_undefined_and_unused_fields(library: content.Library) -> None:
    target = library["prompts"][1]
    target["prompt"] += " {{oops}}"
    target["fields"].append({"key": "spare", "label": "Spare", "hint": "unused"})
    errors = checker.check_structure(library)
    assert f"{target['id']}: template uses {{{{oops}}}} but no field defines it" in errors
    assert f"{target['id']}: field 'spare' is defined but never used" in errors


def test_structure_rules(library: content.Library) -> None:
    first, second = library["prompts"][0], library["prompts"][1]
    second["id"] = first["id"]
    second["number"] = first["number"]
    first["color"] = "chartreuse"
    first["next_steps"] = ["only one"]
    del first["cta"]  # type: ignore[misc]
    library["fixes"][0]["color"] = "nope"
    errors = checker.check_structure(library)
    for expected in (
        "duplicate id",
        "duplicate number",
        "unknown color 'chartreuse'",
        "needs exactly 3 next steps",
        "missing 'cta'",
    ):
        assert any(expected in e for e in errors), expected
    assert any(e.startswith("fix ") for e in errors)


def test_markdown_skips_code_and_ignore_regions() -> None:
    text = "\n".join(
        [
            "Fine line",
            "```",
            "code can say delve",
            "```",
            "<!-- lint-ignore-start -->",
            "Example: leverage",
            "<!-- lint-ignore-end -->",
            "But this line will unlock trouble",
        ]
    )
    assert checker.check_markdown(text, "DOC.md") == ["DOC.md:8: contains 'unlock'"]


def test_docs_are_checked(library: content.Library, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("All good here.\nA game-changer.\n", encoding="utf-8")
    assert checker.check_copy(library, docs_root=tmp_path) == ["README.md:2: contains 'game-changer'"]


def test_empty_linkedin_is_a_warning_not_an_error(library: content.Library) -> None:
    library["author"]["linkedin"] = ""
    report = checker.run(library)
    assert report.ok
    assert any("linkedin" in w for w in report.warnings)
    library["author"]["linkedin"] = "https://www.linkedin.com/in/example"
    assert checker.run(library).warnings == []


def test_walk_skips_private_keys() -> None:
    assert list(checker.walk({"a": ["x", {"b": "y"}], "_c": "z"})) == [("a[0]", "x"), ("a[1].b", "y")]
