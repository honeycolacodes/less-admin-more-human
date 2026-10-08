# Shortcuts. Run `make install` once, then `make quality` before you push.
PY ?= python3

.PHONY: install all check prompts pdf site serve eval eval-dry test lint format typecheck quality clean

install:   ; $(PY) -m pip install -e ".[dev]" && $(PY) -m playwright install chromium && pre-commit install

all:       ; lamh all
check:     ; lamh check
prompts:   ; lamh prompts
pdf:       ; lamh pdf
site:      ; lamh site
serve:     ; lamh site --serve
eval:      ; lamh eval
eval-dry:  ; lamh eval --dry-run

test:      ; pytest
lint:      ; ruff check . && ruff format --check .
format:    ; ruff check --fix . && ruff format .
typecheck: ; mypy
quality: lint typecheck test

clean:     ; rm -rf build _site .pytest_cache .mypy_cache .ruff_cache .coverage evals/results
