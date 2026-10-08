"""Generate the Markdown prompt pages in prompts/.

CI fails if the committed pages drift from data/prompts.json.
"""

from __future__ import annotations

from pathlib import Path

from lamh import content

OUT_DIR = content.ROOT / "prompts"
NOTICE = "<!-- Generated from data/prompts.json by `lamh prompts`. Edit the data file, not this page. -->"


def filename(prompt: content.Prompt) -> str:
    return f"{prompt['number'].lower()}-{prompt['id']}.md"


def _example_output(example: content.Example) -> str:
    output = example["output"]
    if isinstance(output, list):
        return "\n".join(f"- **{line['lead']}** {line['text']}" for line in output)
    return output


def prompt_page(prompt: content.Prompt, library: content.Library) -> str:
    author = library["author"]
    lines = [
        NOTICE,
        "",
        f"# {prompt['number']} · {prompt['title']}",
        "",
        f"**{prompt['audience']}** · {prompt['time']}",
        "",
        f"> **Use it when:** {prompt['use_when']}  ",
        f"> **Have ready:** {prompt['have_ready']}",
        "",
    ]
    if "blurb" in prompt:
        lines += [prompt["blurb"], ""]
    if "tells" in prompt:
        lines += ["## Watch for these tells", "", *[f"- {tell}" for tell in prompt["tells"]], ""]
    lines += [
        "## Copy this",
        "",
        "```text",
        content.render_text(prompt),
        "```",
        "",
        "Swap every `[bracketed]` part for your own details.",
        "",
        "## Made-up example",
        "",
        f"**You paste:** {prompt['example']['input']}",
        "",
        f"**{prompt['example']['output_label']}:**",
        "",
        _example_output(prompt["example"]),
        "",
        "## Then do this",
        "",
        *[f"- [ ] {step}" for step in prompt["next_steps"]],
        "",
        "---",
        "",
        " · ".join(
            [
                "[All prompts](README.md)",
                "[Fill it in online](../README.md#use-it-online)",
                f"{author['name']}, {author['role']}",
            ]
        ),
        "",
    ]
    return "\n".join(lines)


def _index_row(p: content.Prompt) -> str:
    cells = [p["number"], f"[{p['title']}]({filename(p)})", p["short_audience"], p["time"], p["use_when"]]
    return "| " + " | ".join(cells) + " |"


def index_page(library: content.Library) -> str:
    lines = [
        NOTICE,
        "",
        "# The prompts",
        "",
        "Pick the one that sounds like your week. "
        "Each page has the prompt, a made-up example and three next steps.",
        "",
        "| # | Prompt | For | Time | Use it when |",
        "|---|--------|-----|------|-------------|",
        *[_index_row(p) for p in library["prompts"]],
    ]
    lines += ["", "## Quick fixes when an answer misses", ""]
    for fix in library["fixes"]:
        detail = (
            f"{fix['lead']} {fix.get('text', '')}"
            if "lead" in fix
            else f"Reply with: `{fix.get('reply', '')}`"
        )
        lines.append(f"- **{fix['problem']}.** {detail}")
    lines += ["", "[Back to the main README](../README.md)", ""]
    return "\n".join(lines)


def render_all(library: content.Library) -> dict[str, str]:
    """Return {filename: markdown} for every page, without touching disk."""
    pages = {"README.md": index_page(library)}
    pages.update({filename(p): prompt_page(p, library) for p in library["prompts"]})
    return pages


def build(library: content.Library, out_dir: Path = OUT_DIR) -> list[Path]:
    """Write every page and remove pages for prompts that no longer exist."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = render_all(library)
    written = []
    for name, text in pages.items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    for stale in out_dir.glob("*.md"):
        if stale.name not in pages:
            stale.unlink()
    return written
