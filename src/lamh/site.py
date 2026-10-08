"""Assemble the web tool into _site/, the folder GitHub Pages serves."""

from __future__ import annotations

import functools
import http.server
import shutil
from pathlib import Path

from lamh import content

SITE_SRC = content.ROOT / "site"
OUT_DIR = content.ROOT / "_site"
PDF_PATH = content.ROOT / "dist" / "less-admin-more-human.pdf"


def build(out_dir: Path = OUT_DIR, pdf: Path = PDF_PATH, data_file: Path = content.DATA_FILE) -> list[str]:
    """Copy the site, the data file and the PDF into out_dir. Returns any notes for the user."""
    notes: list[str] = []
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(SITE_SRC, out_dir)
    (out_dir / "data").mkdir()
    shutil.copy2(data_file, out_dir / "data" / "prompts.json")
    if pdf.exists():
        shutil.copy2(pdf, out_dir / pdf.name)
    else:
        notes.append("dist/ has no PDF yet, so the download link will 404. Run `lamh pdf` first.")
    (out_dir / ".nojekyll").touch()
    return notes


def serve(out_dir: Path = OUT_DIR, port: int = 8000) -> None:  # pragma: no cover
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Previewing at http://localhost:{port}  (Ctrl+C to stop)")
        server.serve_forever()
