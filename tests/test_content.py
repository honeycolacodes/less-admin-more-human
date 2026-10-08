from __future__ import annotations

import pytest

from lamh import content


def test_field_keys_in_order_without_duplicates(prompt: content.Prompt) -> None:
    assert content.field_keys(prompt["prompt"]) == ["notes", "audience"]


def test_unfilled_fields_become_hints(prompt: content.Prompt) -> None:
    assert content.segments(prompt) == [
        ("text", "Summarize "),
        ("field", "paste notes"),
        ("text", " for "),
        ("field", "who reads it"),
        ("text", ".\nNOTES AGAIN: "),
        ("field", "paste notes"),
    ]


def test_filled_fields_become_text_and_repeat(prompt: content.Prompt) -> None:
    text = content.render_text(prompt, {"notes": "Q3 numbers", "audience": "the board"})
    assert text == "Summarize Q3 numbers for the board.\nNOTES AGAIN: Q3 numbers"


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_whitespace_only_values_count_as_blank(prompt: content.Prompt, blank: str) -> None:
    assert content.render_text(prompt, {"notes": blank}).startswith("Summarize [paste notes]")


def test_values_are_trimmed_and_not_re_expanded(prompt: content.Prompt) -> None:
    text = content.render_text(prompt, {"notes": "  {{audience}} $1  ", "audience": "x"})
    assert text.startswith("Summarize {{audience}} $1 for x.")


def test_every_real_prompt_renders_without_leftover_braces(real_library: content.Library) -> None:
    for prompt in real_library["prompts"]:
        rendered = content.render_text(prompt)
        assert "{{" not in rendered, prompt["id"]
        assert "}}" not in rendered, prompt["id"]
        for field in prompt["fields"]:
            assert f"[{field['hint']}]" in rendered


def test_main_and_bonus_split(real_library: content.Library) -> None:
    mains, bonus = content.main_prompts(real_library), content.bonus_prompts(real_library)
    assert len(mains) == 4
    assert {p["id"] for p in bonus} == {"strip-ai-tells", "match-my-voice"}
    assert len(mains) + len(bonus) == len(real_library["prompts"])


def test_get_prompt(real_library: content.Library) -> None:
    assert content.get_prompt(real_library, "follow-up")["number"] == "04"
    with pytest.raises(KeyError, match="nope"):
        content.get_prompt(real_library, "nope")


def test_load_reads_a_given_path(write_library, real_library: content.Library) -> None:
    path = write_library(real_library)
    assert content.load(path) == real_library
