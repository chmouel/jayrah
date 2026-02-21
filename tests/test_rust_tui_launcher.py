"""Tests for Rust TUI launcher integration helpers."""

from pathlib import Path
from types import SimpleNamespace

import click
import pytest

from jayrah.ui import rust_tui


def test_run_rust_browser_passes_query_to_cargo(monkeypatch):
    """run_rust_browser should call cargo with query forwarding."""
    captured = {}

    def fake_run(command, cwd, env, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    result = rust_tui.run_rust_browser({}, query="project = TEST")

    assert result is None
    assert "--query" in captured["command"]
    assert "project = TEST" in captured["command"]
    assert captured["check"] is False
    assert Path(captured["cwd"]).name == "jayrah"


def test_run_rust_browser_passes_layout_and_zoom_to_cargo(monkeypatch):
    """run_rust_browser should forward startup layout and zoom flags."""
    captured = {}

    def fake_run(command, cwd, env, check):
        captured["command"] = command
        _ = cwd, env, check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    result = rust_tui.run_rust_browser({}, layout="vertical", zoom="detail")

    assert result is None
    assert "--layout" in captured["command"]
    assert "vertical" in captured["command"]
    assert "--zoom" in captured["command"]
    assert "detail" in captured["command"]


def test_run_rust_browser_choose_mode_reads_and_cleans_output(monkeypatch):
    """Choose mode should parse selected key from env-file and remove temp file."""
    captured = {}

    def fake_run(command, cwd, env, check):
        _ = command, cwd, check
        output_path = env["JAYRAH_TUI_CHOOSE_FILE"]
        captured["output_path"] = output_path
        Path(output_path).write_text("TEST-777\n", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    result = rust_tui.run_rust_browser({}, query="project = TEST", choose_mode=True)

    assert result == "TEST-777"
    assert "output_path" in captured
    assert not Path(captured["output_path"]).exists()


def test_run_rust_browser_raises_on_non_zero_exit(monkeypatch):
    """Launcher should surface non-zero cargo exits as ClickException."""

    def fake_run(command, cwd, env, check):
        _ = command, cwd, env, check
        return SimpleNamespace(returncode=42)

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    with pytest.raises(click.ClickException) as exc:
        rust_tui.run_rust_browser({})

    assert "status 42" in str(exc.value)


def test_run_rust_browser_non_zero_exit_cleans_choose_tempfile(monkeypatch):
    """Non-zero exits in choose mode should still remove temporary output file."""
    captured = {}

    def fake_run(command, cwd, env, check):
        _ = command, cwd, check
        output_path = env["JAYRAH_TUI_CHOOSE_FILE"]
        captured["output_path"] = output_path
        Path(output_path).write_text("stale\n", encoding="utf-8")
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    with pytest.raises(click.ClickException) as exc:
        rust_tui.run_rust_browser({}, choose_mode=True)

    assert "status 7" in str(exc.value)
    assert "output_path" in captured
    assert not Path(captured["output_path"]).exists()


def test_run_rust_browser_raises_when_cargo_missing(monkeypatch):
    """Launcher should raise a clear error when cargo is not available."""

    def fake_run(command, cwd, env, check):
        _ = command, cwd, env, check
        raise FileNotFoundError("cargo")

    monkeypatch.setattr(rust_tui.subprocess, "run", fake_run)

    with pytest.raises(click.ClickException) as exc:
        rust_tui.run_rust_browser({})

    assert "cargo" in str(exc.value).lower()
