"""Rust Ratatouille launcher helpers for browse integration."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import click


def run_rust_browser(
    config: dict,
    query: str | None = None,
    choose_mode: bool = False,
) -> str | None:
    """Run the Rust TUI and optionally return a selected key in choose mode."""
    _ = config
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "rust" / "Cargo.toml"

    if not manifest_path.exists():
        raise click.ClickException(
            f"Rust workspace not found: {manifest_path}. Run from the repository checkout."
        )

    command = [
        "cargo",
        "run",
        "-p",
        "jayrah-tui",
        "--manifest-path",
        str(manifest_path),
        "--",
    ]
    if query:
        command.extend(["--query", query])
    if choose_mode:
        command.append("--choose")

    env = os.environ.copy()
    choose_output_path = None
    if choose_mode:
        fd, choose_output_path = tempfile.mkstemp(
            prefix="jayrah-rust-choose-", suffix=".txt"
        )
        os.close(fd)
        env["JAYRAH_TUI_CHOOSE_FILE"] = choose_output_path

    try:
        completed = subprocess.run(command, cwd=repo_root, env=env, check=False)
    except FileNotFoundError as error:
        if choose_output_path:
            Path(choose_output_path).unlink(missing_ok=True)
        raise click.ClickException(
            "Unable to launch Rust TUI: 'cargo' was not found in PATH."
        ) from error

    if completed.returncode != 0:
        if choose_output_path:
            Path(choose_output_path).unlink(missing_ok=True)
        raise click.ClickException(
            f"Rust TUI exited with status {completed.returncode}."
        )

    if not choose_mode or not choose_output_path:
        return None

    try:
        selected_key = Path(choose_output_path).read_text(encoding="utf-8").strip()
    finally:
        Path(choose_output_path).unlink(missing_ok=True)

    return selected_key or None
