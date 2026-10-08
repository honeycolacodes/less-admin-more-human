"""Build the printable PDF guide and the README preview image.

The guide is HTML and CSS (guide/templates, guide/guide.css) rendered to PDF by
headless Chromium. Every page is a fixed US Letter sheet, so the build measures
each page and refuses to export one whose content runs past the edge.
"""

from __future__ import annotations

import asyncio
import copy
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader

from lamh import content

GUIDE_DIR = content.ROOT / "guide"
BUILD_DIR = content.ROOT / "build"
PDF_PATH = content.ROOT / "dist" / "less-admin-more-human.pdf"
PREVIEW_PATH = content.ROOT / "assets" / "preview.png"
PAGE_W, PAGE_H = 816, 1056  # US Letter at 96 px per inch
LINKEDIN_PLACEHOLDER = "[YOUR LINKEDIN URL]"


class PageOverflowError(RuntimeError):
    """Raised when content is taller than its sheet and would be cut off."""

    def __init__(self, overflows: list[dict[str, int]]) -> None:
        self.overflows = overflows
        detail = ", ".join(f"page {o['page']} by {o['over']}px" for o in overflows)
        super().__init__(f"Content overflows its sheet: {detail}")


def page_plan(library: content.Library) -> list[dict[str, Any]]:
    """Decide the page order and number every page.

    Prompt pages get their page number written onto the prompt, so the
    "Start here" tiles always point at the right page.
    """
    pages: list[dict[str, Any]] = [{"template": "cover"}, {"template": "start"}]
    for index, prompt in enumerate(content.main_prompts(library)):
        pages.append({"template": "prompt", "prompt": prompt, "index": index})
    pages += [{"template": "bonus"}, {"template": "fixes"}]
    for number, page in enumerate(pages, start=1):
        page["number"], page["total"] = number, len(pages)
        if "prompt" in page:
            page["prompt"]["page"] = number
    return pages


def linkedin_display(url: str) -> str:
    url = url.strip()
    return url.removeprefix("https://").removeprefix("http://").removeprefix("www.") or LINKEDIN_PLACEHOLDER


def render_html(library: content.Library) -> str:
    """Render the whole guide as one HTML document, one <section class="page"> per sheet."""
    data: dict[str, Any] = copy.deepcopy(dict(library))
    for prompt in data["prompts"]:
        prompt["segments"] = content.segments(prompt)
    typed = cast(content.Library, data)
    env = Environment(
        loader=FileSystemLoader(GUIDE_DIR / "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("guide.html.j2").render(
        **data,
        pages=page_plan(typed),
        main_prompts=content.main_prompts(typed),
        bonus_prompts=content.bonus_prompts(typed),
        linkedin_display=linkedin_display(data["author"].get("linkedin", "")),
        stylesheet=(GUIDE_DIR / "guide.css").as_uri(),
    )


async def export(html_path: Path, pdf_path: Path, shots_dir: Path | None) -> list[Path]:  # pragma: no cover
    """Print the HTML to PDF with Chromium and optionally screenshot each page."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": PAGE_W, "height": PAGE_H}, device_scale_factor=2)
            await page.goto(html_path.as_uri())
            await page.evaluate("document.fonts.ready")
            overflows: list[dict[str, int]] = await page.evaluate(
                """() => [...document.querySelectorAll('.page')]
                     .map((el, i) => ({ page: i + 1, over: el.scrollHeight - el.clientHeight }))
                     .filter(p => p.over > 0)"""
            )
            if overflows:
                raise PageOverflowError(overflows)

            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            await page.pdf(
                path=str(pdf_path), width=f"{PAGE_W}px", height=f"{PAGE_H}px", print_background=True
            )

            shots: list[Path] = []
            if shots_dir:
                shots_dir.mkdir(parents=True, exist_ok=True)
                sheets = page.locator(".page")
                for i in range(await sheets.count()):
                    shot = shots_dir / f"page-{i + 1:02d}.png"
                    await sheets.nth(i).screenshot(path=str(shot))
                    shots.append(shot)
            return shots
        finally:
            await browser.close()


def contact_sheet(
    shots: list[Path], out_path: Path, cols: int = 4, scale: float = 0.5, gap: int = 24
) -> Path:
    """Lay page screenshots out in a grid on a light background."""
    from PIL import Image

    tile_w, tile_h = int(PAGE_W * scale), int(PAGE_H * scale)
    rows = -(-len(shots) // cols)
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * gap, rows * tile_h + (rows + 1) * gap), "#e9e7ef")
    for i, shot in enumerate(shots):
        with Image.open(shot) as img:
            tile = img.convert("RGB").resize((tile_w, tile_h), Image.Resampling.LANCZOS)
        sheet.paste(tile, (gap + (i % cols) * (tile_w + gap), gap + (i // cols) * (tile_h + gap)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, optimize=True)
    return out_path


def build(library: content.Library, preview: bool = True) -> list[Path]:  # pragma: no cover
    """Render, export the PDF and (optionally) the preview. Returns the files written."""
    BUILD_DIR.mkdir(exist_ok=True)
    html_path = BUILD_DIR / "guide.html"
    html_path.write_text(render_html(library), encoding="utf-8")
    shots = asyncio.run(export(html_path, PDF_PATH, BUILD_DIR / "pages" if preview else None))
    written = [PDF_PATH]
    if shots:
        written.append(contact_sheet(shots, PREVIEW_PATH))
    return written
