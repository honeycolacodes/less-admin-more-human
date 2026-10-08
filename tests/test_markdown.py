from __future__ import annotations

from pathlib import Path

from lamh import content, markdown


def test_committed_pages_match_the_data(real_library: content.Library) -> None:
    """The same guarantee CI enforces: prompts/ is never stale."""
    for name, text in markdown.render_all(real_library).items():
        committed = markdown.OUT_DIR / name
        assert committed.exists(), f"prompts/{name} is missing. Run `lamh prompts`."
        assert committed.read_text(encoding="utf-8") == text, f"prompts/{name} is stale. Run `lamh prompts`."


def test_build_writes_pages_and_removes_stale_ones(real_library: content.Library, tmp_path: Path) -> None:
    (tmp_path / "old-prompt.md").write_text("gone soon", encoding="utf-8")
    written = markdown.build(real_library, tmp_path)
    names = {p.name for p in written}
    assert names == {"README.md", *(markdown.filename(p) for p in real_library["prompts"])}
    assert not (tmp_path / "old-prompt.md").exists()


def test_prompt_page_contents(real_library: content.Library) -> None:
    follow_up = content.get_prompt(real_library, "follow-up")
    page = markdown.prompt_page(follow_up, real_library)
    assert page.startswith(markdown.NOTICE)
    assert content.render_text(follow_up) in page
    assert "- **Maybe:** Lee joins." in page  # list-style example output
    assert page.count("- [ ] ") == 3


def test_bonus_pages_show_blurb_and_tells(real_library: content.Library) -> None:
    strip = markdown.prompt_page(content.get_prompt(real_library, "strip-ai-tells"), real_library)
    voice = markdown.prompt_page(content.get_prompt(real_library, "match-my-voice"), real_library)
    assert "## Watch for these tells" in strip
    assert "It picks up your words" in voice


def test_index_links_every_prompt(real_library: content.Library) -> None:
    index = markdown.index_page(real_library)
    for prompt in real_library["prompts"]:
        assert f"]({markdown.filename(prompt)})" in index
    assert "Reply with: `Keep only the three things" in index
