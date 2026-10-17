# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Metric reference generated from the registry (ADR 0003).

`python -m untraded.metrics.docs` rewrites `docs/metrics-reference.md` (UTF-8, LF line endings,
from the repository root); a test fails when the file and the registry drift apart.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from untraded.metrics import REGISTRY

SECTIONS = {
    "base": "Base",
    "duel": "Duels",
    "trade": "Trades",
    "clutch": "Clutches",
    "pos": "Positioning",
    "util": "Utility",
    "eco": "Economy",
    "rating": "Ratings",
}


def render() -> str:
    lines = [
        "# Metric reference",
        "",
        "*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by "
        "hand. The human-written specification is [metrics-v1.md](metrics-v1.md).*",
        "",
    ]
    for prefix, title in SECTIONS.items():
        metrics = sorted(
            (m for m in REGISTRY.values() if m.id.split(".")[0] == prefix), key=lambda m: m.id
        )
        if not metrics:
            continue
        lines += [
            f"## {title}",
            "",
            "| ID | Version | Name | Unit | Definition | Parameters | Reads |",
            "|---|---|---|---|---|---|---|",
        ]
        for m in metrics:
            params = ", ".join(f"`{k} = {json.dumps(v)}`" for k, v in m.params.items()) or "—"
            uses = ", ".join(f"`{t}`" for t in m.uses) or "—"
            lines.append(
                f"| `{m.id}` | {m.version} | {m.name} | {m.unit} | {m.doc} | {params} | {uses} |"
            )
        lines.append("")
    return "\n".join(lines)


REFERENCE = Path("docs") / "metrics-reference.md"


def write(path: Path = REFERENCE) -> None:
    path.write_text(render(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write(Path(sys.argv[1]) if len(sys.argv) > 1 else REFERENCE)
