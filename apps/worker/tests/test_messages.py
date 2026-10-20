# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""The web's messages cover every advice rule and action the worker can write."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from untraded.advice import RULES

MESSAGES = Path(__file__).parents[2] / "web" / "messages"
LANGUAGES = ["en", "fr"]


def load(lang: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((MESSAGES / f"{lang}.json").read_text(encoding="utf-8"))
    return data


def at(messages: dict[str, Any], dotted: str) -> Any:
    node: Any = messages
    for part in dotted.split("."):
        node = node[part]
    return node


def keys(node: Any, prefix: str = "") -> set[str]:
    if not isinstance(node, dict):
        return {prefix}
    return {k for name, child in node.items() for k in keys(child, f"{prefix}.{name}".lstrip("."))}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_rule_speaks_in_both_tones(lang: str) -> None:
    messages = load(lang)
    for rule in RULES.values():
        for tone in ("coach", "analyst"):
            text = at(messages, f"advice.rules.{rule.id}.{tone}")
            assert "{events}" in text or "{zone}" in text, (rule.id, tone)


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_action_is_in_the_catalog(lang: str) -> None:
    messages = load(lang)
    for rule in RULES.values():
        for action in rule.actions:
            kind = action.split(".")[0]
            assert at(messages, f"actions.kinds.{kind}")
            assert at(messages, f"actions.{action}.title"), action
            assert len(at(messages, f"actions.{action}.how")) > 40, action


def test_both_languages_have_the_same_messages() -> None:
    english, french = (keys(load(lang)) for lang in LANGUAGES)
    assert english == french


def test_placeholders_match_between_languages() -> None:
    english, french = (load(lang) for lang in LANGUAGES)
    for key in keys(english):
        found = [set(re.findall(r"\{(\w+)", str(at(m, key)))) for m in (english, french)]
        assert found[0] == found[1], key
