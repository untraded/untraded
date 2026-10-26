# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""The command line on a console that is not UTF-8 (a Windows code page)."""

from __future__ import annotations

import argparse
import io
import sys

import pytest

from untraded import cli


def cp1252(monkeypatch: pytest.MonkeyPatch) -> io.BytesIO:
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
    monkeypatch.setattr("sys.stdout", console)
    return raw


def commands() -> list[list[str]]:
    """The command and every subcommand, nested ones included."""
    found: list[list[str]] = [[]]

    def walk(parser: argparse.ArgumentParser, prefix: list[str]) -> None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    found.append([*prefix, name])
                    walk(sub, [*prefix, name])

    walk(cli._parser(), [])
    return found


@pytest.mark.parametrize("command", commands(), ids=lambda c: " ".join(c) or "untraded")
def test_every_help_prints_on_a_code_page(
    monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    cp1252(monkeypatch)
    with pytest.raises(SystemExit) as exit_:
        cli.main([*command, "--help"])
    assert exit_.value.code == 0


def test_what_the_code_page_cannot_show_becomes_a_question_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = cp1252(monkeypatch)
    cli._tolerant_output()
    print("Ж \U0001f3af é", file=sys.stdout)
    sys.stdout.flush()
    assert raw.getvalue().decode("cp1252") == "? ? é\n"
