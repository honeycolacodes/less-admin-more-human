from __future__ import annotations

import json
from pathlib import Path

import pytest

from lamh import __version__, cli, content


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["check"]) == 0
    assert "All good" in capsys.readouterr().out


def test_check_fails_on_bad_data(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    real = content.load()
    real["prompts"][0]["use_when"] = "Let us delve in."
    monkeypatch.setattr(content, "load", lambda path=None: real)
    assert cli.main(["check"]) == 1
    assert "contains 'delve'" in capsys.readouterr().out


def test_prompts_writes_to_a_folder(tmp_path: Path) -> None:
    assert cli.main(["prompts", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "README.md").exists()


def test_site_builds_to_a_folder(tmp_path: Path) -> None:
    assert cli.main(["site", "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "index.html").exists()


def test_eval_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["eval", "--dry-run", "--only", "follow-up"]) == 0
    out = capsys.readouterr().out
    assert "=== follow-up/keeps-maybes-separate ===" in out
    assert "recruiter-call-prep" not in out


def test_eval_unknown_prompt(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["eval", "--dry-run", "--only", "nope"]) == 1
    assert "no eval cases for nope" in capsys.readouterr().out


def test_eval_bad_cases_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "cases.yaml"
    bad.write_text("- prompt: nope\n  name: x\n  inputs: {}\n  checks: [{max_words: 3}]\n", encoding="utf-8")
    assert cli.main(["eval", "--cases", str(bad)]) == 1
    assert "no prompt with id 'nope'" in capsys.readouterr().out


def test_eval_without_a_key(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert cli.main(["eval"]) == 2
    assert cli.main(["eval", "--skip-if-no-key"]) == 0
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().out


def test_eval_with_a_client_writes_results_and_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_client_class, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    out = tmp_path / "results.json"
    answer = "Agreed\n- Sam: brief Friday\nStill open\n- Comp\nNext steps\n- Lee may join (to confirm)"
    code = cli.main(
        ["eval", "--only", "follow-up", "--out", str(out), "--workers", "1"],
        client_factory=lambda: fake_client_class(answer=answer),
    )
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["cases"]["total"] == 2
    assert summary.read_text(encoding="utf-8").startswith("## Prompt evals")
    assert "Full results:" in capsys.readouterr().out


def test_eval_below_threshold_fails(tmp_path: Path, fake_client_class) -> None:
    code = cli.main(
        ["eval", "--only", "follow-up", "--out", str(tmp_path / "r.json"), "--min-pass-rate", "0.99"],
        client_factory=lambda: fake_client_class(
            answer="Too short.", grade='{"pass": false, "reason": "no"}'
        ),
    )
    assert code == 1
