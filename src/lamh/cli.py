"""The `lamh` command: one entry point for checking, building and evaluating.

lamh check              validate the data file and copy
lamh prompts            regenerate prompts/*.md
lamh pdf                build the PDF guide and preview image
lamh site [--serve]     assemble the web tool into _site/
lamh eval [--dry-run]   run the prompt evals against Claude
lamh all                check, prompts, pdf, site
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from lamh import __version__, content
from lamh.evals.client import ModelClient

ClientFactory = Callable[[], ModelClient]
Handler = Callable[[argparse.Namespace], int]


def cmd_check(_: argparse.Namespace) -> int:
    from lamh import checker

    library = content.load()
    report = checker.run(library)
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")
    if not report.ok:
        print(f"\n{len(report.errors)} problem(s) found.")
        return 1
    print(f"All good: {len(library['prompts'])} prompts, no AI tells.")
    return 0


def cmd_prompts(args: argparse.Namespace) -> int:
    from lamh import markdown

    written = markdown.build(content.load(), Path(args.out))
    print(f"Wrote {len(written)} Markdown pages to {args.out}")
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:  # pragma: no cover - needs a browser
    from lamh import guide

    try:
        written = guide.build(content.load(), preview=not args.no_preview)
    except guide.PageOverflowError as error:
        print(f"error: {error}")
        return 1
    for path in written:
        print(f"Wrote {path.relative_to(content.ROOT)}")
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    from lamh import site

    out = Path(args.out)
    for note in site.build(out):
        print(f"note: {note}")
    print(f"Wrote {out}")
    if args.serve:  # pragma: no cover
        site.serve(out, args.port)
    return 0


def cmd_eval(args: argparse.Namespace, client_factory: ClientFactory | None = None) -> int:
    from lamh.evals import cases as eval_cases
    from lamh.evals import runner

    library = content.load()
    try:
        cases = eval_cases.load_cases(Path(args.cases), library)
    except eval_cases.CaseError as error:
        print(f"error: {error}")
        return 1
    if args.only:
        unknown = set(args.only) - {c.prompt_id for c in cases}
        if unknown:
            print(f"error: no eval cases for {', '.join(sorted(unknown))}")
            return 1
        cases = [c for c in cases if c.prompt_id in args.only]

    if args.dry_run:
        print(runner.dry_run(cases, library))
        return 0

    if client_factory is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set, so the evals cannot call the model.")
            print("Set it, or run `lamh eval --dry-run` to see what would be sent.")
            return 0 if args.skip_if_no_key else 2
        from lamh.evals.client import AnthropicClient

        client_factory = AnthropicClient  # pragma: no cover

    report = runner.run(
        cases,
        library,
        client_factory(),
        model=args.model,
        grader_model=args.grader_model,
        workers=args.workers,
    )
    print(report.to_console())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nFull results: {out}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report.to_markdown())

    if report.pass_rate < args.min_pass_rate:
        print(f"Pass rate {report.pass_rate:.0%} is below the {args.min_pass_rate:.0%} threshold.")
        return 1
    return 0


def cmd_all(args: argparse.Namespace) -> int:  # pragma: no cover - runs the browser build
    from lamh import markdown, site

    if cmd_check(args):
        return 1
    markdown.build(content.load())
    if cmd_pdf(argparse.Namespace(no_preview=False)):
        return 1
    site.build()
    print("Built prompts/, dist/, assets/ and _site/")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from lamh import markdown, site
    from lamh.evals import cases as eval_cases
    from lamh.evals import runner

    parser = argparse.ArgumentParser(
        prog="lamh", description="Less admin. More human. Build and test the prompt library."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="validate data/prompts.json and check copy for AI tells").set_defaults(
        func=cmd_check
    )

    p = sub.add_parser("prompts", help="regenerate the Markdown prompt pages")
    p.add_argument("--out", default=str(markdown.OUT_DIR), help="output folder (default: prompts/)")
    p.set_defaults(func=cmd_prompts)

    p = sub.add_parser("pdf", help="build the PDF guide and the README preview image")
    p.add_argument("--no-preview", action="store_true", help="skip assets/preview.png")
    p.set_defaults(func=cmd_pdf)

    p = sub.add_parser("site", help="assemble the web tool for GitHub Pages")
    p.add_argument("--out", default=str(site.OUT_DIR))
    p.add_argument("--serve", action="store_true", help="preview locally after building")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("eval", help="run the prompt evals against Claude")
    p.add_argument("--cases", default=str(eval_cases.CASES_FILE))
    p.add_argument("--only", nargs="+", metavar="PROMPT_ID", help="only run cases for these prompts")
    p.add_argument("--model", default=runner.DEFAULT_MODEL, help="model that answers the prompts")
    p.add_argument("--grader-model", default=runner.DEFAULT_GRADER, help="model that grades rubric checks")
    p.add_argument("--workers", type=int, default=4, help="cases to run in parallel")
    p.add_argument("--min-pass-rate", type=float, default=0.9, help="fail below this share of passing checks")
    p.add_argument("--out", default=str(content.ROOT / "evals" / "results" / "latest.json"))
    p.add_argument("--dry-run", action="store_true", help="show prompts and checks without calling a model")
    p.add_argument("--skip-if-no-key", action="store_true", help="exit 0 instead of 2 when no API key is set")
    p.set_defaults(func=cmd_eval)

    sub.add_parser("all", help="check, then build prompts, PDF and site").set_defaults(func=cmd_all)
    return parser


def main(argv: Sequence[str] | None = None, *, client_factory: ClientFactory | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "eval":
        return cmd_eval(args, client_factory)
    handler: Handler = args.func
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
