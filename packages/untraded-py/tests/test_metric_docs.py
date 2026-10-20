# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Generated metric pages (E10): in sync with the registry, the parameters, the notes and the
human-written specification."""

from __future__ import annotations

import itertools
import re
from pathlib import Path

from untraded.derive.buys import BuyThresholds
from untraded.derive.players import SETUP_OFFSET_S
from untraded.metrics import REGISTRY
from untraded.metrics.docs import SECTIONS, render
from untraded.metrics.notes import CHANGES, FAMILY_LIMITS, FIRST_PR, LIMITS, history
from untraded.metrics.params import PARAMETERS

ROOT = Path(__file__).parents[3]
PAGES = ROOT / "docs" / "metrics"
EXAMPLE = ROOT / "packages" / "untraded-py" / "tests" / "fixtures" / "premier-half"


def test_pages_are_up_to_date() -> None:
    pages = render(EXAMPLE)
    on_disk = {p.name: p.read_text(encoding="utf-8") for p in PAGES.glob("*.md")}
    hint = "run `python -m untraded.metrics.docs` from the repository root"
    assert sorted(on_disk) == sorted(pages), hint
    for name, text in pages.items():
        assert on_disk[name] == text, f"{name}: {hint}"


def test_one_page_per_metric_with_every_section() -> None:
    pages = render(EXAMPLE)
    assert {f"{m}.md" for m in REGISTRY} | {"README.md", "parameters.md"} == set(pages)
    for metric_id in REGISTRY:
        page = pages[f"{metric_id}.md"]
        for section in ("## Definition", "## Example", "## Limits", "## History"):
            assert section in page, f"{metric_id}: no {section}"


def test_every_metric_parameter_is_declared_with_the_same_default() -> None:
    for m in REGISTRY.values():
        for key, default in m.params.items():
            assert key in PARAMETERS, f"{m.id}: parameter {key} is not in PARAMETERS"
            assert PARAMETERS[key].default == default, f"{m.id}: default of {key}"


def test_derivation_parameters_follow_the_code() -> None:
    buy = BuyThresholds()
    assert PARAMETERS["setup.offset_s"].default == SETUP_OFFSET_S
    assert PARAMETERS["buy.eco_max"].default == buy.eco_max
    assert PARAMETERS["buy.full_min_ct"].default == buy.full_min_ct
    assert PARAMETERS["buy.full_min_t"].default == buy.full_min_t
    used = {key for m in REGISTRY.values() for key in m.params}
    for p in PARAMETERS.values():
        assert (p.stage == "metric") == (p.id in used), f"{p.id}: stage {p.stage}"


def test_notes_name_registered_metrics_and_families() -> None:
    assert set(LIMITS) <= set(REGISTRY)
    assert set(CHANGES) <= set(REGISTRY)
    assert set(FAMILY_LIMITS) <= set(SECTIONS) == set(FIRST_PR)


def test_every_version_says_what_changed() -> None:
    for m in REGISTRY.values():
        versions = [v for v, _ in history(m.id, m.version)]
        assert m.version in versions, f"{m.id} {m.version}: add it to notes.CHANGES"
        assert versions[-1] == m.version, f"{m.id}: notes.CHANGES has a version above {m.version}"


def test_the_specification_lists_exactly_the_registered_metrics() -> None:
    """docs/metrics-v1.md and the registry must not drift apart (CLAUDE.md rule 4)."""
    spec = (ROOT / "docs" / "metrics-v1.md").read_text(encoding="utf-8")
    listed: set[str] = set()
    families = "|".join(SECTIONS)
    for token in re.findall(rf"`((?:{families})\.[a-z0-9_{{}}.,]+)`", spec):
        listed |= _expand(token)
    # "A 3-second variant is computed alongside with the `_w3` suffix" (metrics-v1 § 2).
    listed |= {f"{i}_w3" for i in listed if f"{i}_w3" in REGISTRY}
    assert sorted(set(REGISTRY) - listed) == [], "registered but not in metrics-v1"
    assert sorted(listed - set(REGISTRY)) == [], "in metrics-v1 but not registered"


def _expand(token: str) -> set[str]:
    """`base.multikills_{1..5}` and `util.thrown_{flash,he}` into their ids."""
    parts = re.split(r"\{([^}]*)\}", token)
    choices: list[list[str]] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            choices.append([part])
        elif ".." in part:
            low, high = part.split("..")
            choices.append([str(n) for n in range(int(low), int(high) + 1)])
        else:
            choices.append(part.split(","))
    return {"".join(c) for c in itertools.product(*choices)}
