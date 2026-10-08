from __future__ import annotations

import re
from pathlib import Path

import pytest

from lamh import content, guide


def test_page_plan_numbers_pages_and_links_prompts(library: content.Library) -> None:
    pages = guide.page_plan(library)
    assert [p["template"] for p in pages] == [
        "cover",
        "start",
        "prompt",
        "prompt",
        "prompt",
        "prompt",
        "bonus",
        "fixes",
    ]
    assert [p["number"] for p in pages] == list(range(1, 9))
    assert all(p["total"] == 8 for p in pages)
    prompt_pages = [p for p in pages if p["template"] == "prompt"]
    assert [p["prompt"]["page"] for p in prompt_pages] == [3, 4, 5, 6]


def test_render_html_has_one_section_per_page(library: content.Library) -> None:
    html = guide.render_html(library)
    assert len(re.findall(r'<section class="page', html)) == 8
    assert "{{" not in html
    assert "{%" not in html
    assert "PAGE 3" in html
    assert "PAGE 6" in html  # start-page tiles point at prompt pages
    assert "08 / 08" in html


def test_render_html_marks_every_blank(library: content.Library) -> None:
    html = guide.render_html(library)
    for prompt in library["prompts"]:
        for field in prompt["fields"]:
            assert f'<span class="fill">[{field["hint"]}]</span>' in html


def test_render_html_escapes_content(library: content.Library) -> None:
    library["prompts"][0]["title"] = "<script>alert(1)</script>"
    html = guide.render_html(library)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("", guide.LINKEDIN_PLACEHOLDER),
        ("   ", guide.LINKEDIN_PLACEHOLDER),
        ("https://www.linkedin.com/in/example", "linkedin.com/in/example"),
        ("http://linkedin.com/in/example", "linkedin.com/in/example"),
    ],
)
def test_linkedin_display(url: str, shown: str) -> None:
    assert guide.linkedin_display(url) == shown


def test_linkedin_reaches_the_last_page(library: content.Library) -> None:
    library["author"]["linkedin"] = "https://www.linkedin.com/in/example"
    html = guide.render_html(library)
    assert "linkedin.com/in/example" in html
    assert guide.LINKEDIN_PLACEHOLDER not in html


def test_render_does_not_mutate_the_library(library: content.Library) -> None:
    before = repr(library)
    guide.render_html(library)
    assert repr(library) == before


def test_contact_sheet_lays_out_pages(tmp_path: Path) -> None:
    from PIL import Image

    shots = []
    for i in range(5):
        path = tmp_path / f"page-{i}.png"
        Image.new("RGB", (guide.PAGE_W, guide.PAGE_H), (i * 40, 0, 0)).save(path)
        shots.append(path)
    out = guide.contact_sheet(shots, tmp_path / "sheet.png", cols=4, scale=0.25, gap=10)
    with Image.open(out) as sheet:
        tile_w, tile_h = int(guide.PAGE_W * 0.25), int(guide.PAGE_H * 0.25)
        assert sheet.size == (4 * tile_w + 5 * 10, 2 * tile_h + 3 * 10)


def test_overflow_error_message() -> None:
    error = guide.PageOverflowError([{"page": 7, "over": 4}])
    assert "page 7 by 4px" in str(error)
    assert error.overflows == [{"page": 7, "over": 4}]
