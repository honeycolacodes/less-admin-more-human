from __future__ import annotations

import json
from pathlib import Path

from lamh import content, site


def test_build_assembles_everything_pages_needs(tmp_path: Path) -> None:
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.7 fake")
    out = tmp_path / "_site"
    notes = site.build(out, pdf=pdf)
    assert notes == []
    for name in ("index.html", "app.js", "render.js", "styles.css", "favicon.svg", ".nojekyll", "guide.pdf"):
        assert (out / name).exists(), name
    copied = json.loads((out / "data" / "prompts.json").read_text(encoding="utf-8"))
    assert copied == content.load()


def test_build_replaces_old_output_and_notes_a_missing_pdf(tmp_path: Path) -> None:
    out = tmp_path / "_site"
    out.mkdir()
    (out / "stale.txt").write_text("old", encoding="utf-8")
    notes = site.build(out, pdf=tmp_path / "missing.pdf")
    assert not (out / "stale.txt").exists()
    assert len(notes) == 1
    assert "PDF" in notes[0]


def test_page_loads_scripts_in_order() -> None:
    html = (site.SITE_SRC / "index.html").read_text(encoding="utf-8")
    assert html.index('src="render.js"') < html.index('src="app.js"')
