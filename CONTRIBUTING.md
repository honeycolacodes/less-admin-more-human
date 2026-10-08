# Contributing

Ideas for new prompts, sharper wording and fixes are all welcome. Open an issue first if you are planning something big.

## Set up

```bash
python -m venv .venv && source .venv/bin/activate
make install      # package, dev tools, Chromium and pre-commit hooks
make quality      # lint, type check and tests; run this before you push
```

## How the content is organized

Every prompt, example and line of copy lives in one file: [`data/prompts.json`](data/prompts.json). The PDF, the web tool and the Markdown pages are generated from it. Edit the data file, never the generated pages in `prompts/`.

A prompt looks like this (shortened):

```json
{
  "id": "follow-up",
  "number": "04",
  "color": "sky",
  "title": "Stop rewriting the follow-up.",
  "trigger": "I just got off a call and owe a follow-up.",
  "prompt": "Turn these rough notes into a short follow-up...\n\nNOTES: {{notes}}",
  "fields": [{ "key": "notes", "label": "Notes", "hint": "paste your bullets" }],
  "next_steps": ["Check every name, date and promise", "...", "..."]
}
```

Each `{{field}}` in the prompt becomes a yellow `[hint]` in the PDF and a text box on the site.

## Adding or changing a prompt

1. Edit `data/prompts.json`.
2. Add at least one case for it in [`evals/cases.yaml`](evals/cases.yaml). A test fails if any prompt has no eval case.
3. Check and rebuild:

   ```bash
   lamh check            # structure and AI tells
   lamh eval --dry-run   # confirm your eval case is valid
   make all              # Markdown, PDF and site
   ```

4. Open `dist/less-admin-more-human.pdf` and look at your page. The build stops if a page overflows, so shorten the copy until it fits.
5. If you have an API key, run `lamh eval --only <your-prompt-id>` and make sure it passes.
6. Commit the data file together with the regenerated `prompts/`, `dist/` and `assets/` files.

The PDF has room for four main prompts. A new prompt beyond that works best as a bonus (`"bonus": true`), which shows on the site and in Markdown.

## Writing a good eval case

- **Test the promises the prompt makes.** If it says "under 150 words," add `max_words`. If it says "do not add dates," add `no_new_dates`.
- **Use input that tempts the model to break the rule.** A background that says "no fintech experience" is a better test than one that never mentions fintech.
- **One idea per rubric.** "Keeps compensation open" and "presents Lee as a maybe" are two rubrics, not one.
- **Prefer rule checks when they can do the job.** They are free, fast and never flaky.

## What makes a good prompt here

- **One job per prompt.** If it needs "and also," it is two prompts.
- **Say what not to do.** Most bad AI output comes from filling gaps: invented experience, extra requirements, promises nobody made.
- **Every personal detail is a field.** Never bake in example details the reader has to delete.
- **Three next steps, done by a human.** The prompt drafts. The person decides and sends.
- **Plain words.** The checker fails on long dashes and stock AI phrases. To show one as an example, add its path to that prompt's `_lint_ignore` list.

## Pull request checklist

- [ ] `make quality` passes (lint, mypy, tests)
- [ ] `lamh check` passes
- [ ] Every new or changed prompt has an eval case
- [ ] `prompts/` is regenerated and committed
- [ ] The PDF builds without overflow errors
- [ ] Examples are made up, not real people or companies
