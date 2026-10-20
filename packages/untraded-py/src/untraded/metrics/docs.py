# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: MIT
"""Metric pages generated from the registry (ADR 0003, workstream E10).

`python -m untraded.metrics.docs` rewrites `docs/metrics/` from the repository root: an index, a
page per parameter set and one page per metric with its definition, parameters, a real example on
the `premier-half` fixture, its status against CS Demo Manager, its limits and its history.
A test fails when the pages and the registry drift apart.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import polars as pl

import untraded
from untraded import fixtures
from untraded.derive import derive
from untraded.metrics import REGISTRY, Dataset, compute, compute_table
from untraded.metrics.notes import ALL_LIMITS, FAMILY_LIMITS, LIMITS, history
from untraded.metrics.params import PARAMETERS
from untraded.metrics.registry import Metric
from untraded.validation.csdm import COMPARED

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
DOCS = Path("docs") / "metrics"
EXAMPLE = Path("packages/untraded-py/tests/fixtures/premier-half")
CODE = "https://github.com/untraded/untraded/blob/main/packages/untraded-py/src/untraded"
GENERATED = (
    "*Generated from the metric registry by `python -m untraded.metrics.docs`: do not edit by "
    "hand. The specification is [metrics-v1.md](../metrics-v1.md).*"
)
COMPARED_TOO = {
    "base.assists": "with assists and flash assists added up",
    "base.flash_assists": "with assists and flash assists added up",
    "trade.untraded_deaths": "through deaths and traded deaths, both compared",
    "trade.traded_death_pct": "through deaths and traded deaths, both compared",
}
"""Metrics CS Demo Manager has no field for, checked through the fields it has."""
TABLE_ROWS = 8


def render(example: Path = EXAMPLE) -> dict[str, str]:
    """Every page, by file name."""
    tables = fixtures.read(example)
    ds = Dataset.from_matches([{**tables, **derive(tables).tables()}])
    names = dict(tables["player"].select("steamid", "name").iter_rows())
    values = compute(ds)
    info = tables["match"].row(0, named=True)
    meta = fixtures.read_meta(example)
    where = (
        f"the `{example.name}` fixture: a {info['mode'].capitalize()} match on {info['map']}, "
        f"rounds {meta['rounds'][0]} to {meta['rounds'][1]}, anonymized players"
    )
    pages = {"README.md": _index(), "parameters.md": _parameters()}
    for m in REGISTRY.values():
        if m.kind == "value":
            rows = values.filter(pl.col("metric") == m.id).sort("steamid")
            example_md = _value_example(rows, names, m)
        else:
            example_md = _table_example(compute_table(ds, m.id), names)
        pages[f"{m.id}.md"] = _page(m, example_md, where)
    return pages


def _families() -> list[tuple[str, list[Metric]]]:
    return [
        (
            title,
            sorted((m for m in REGISTRY.values() if m.id.split(".")[0] == p), key=lambda m: m.id),
        )
        for p, title in SECTIONS.items()
    ]


def _index() -> str:
    lines = ["# Metrics", "", GENERATED, ""]
    lines += [
        f"{len(REGISTRY)} metrics, each with its own page. Parameters, their defaults and the "
        "thresholds still to calibrate are on [parameters.md](parameters.md).",
        "",
        "## Shared conventions",
        "",
        *(f"- {limit}" for limit in ALL_LIMITS),
        "",
    ]
    for title, metrics in _families():
        lines += [f"## {title}", "", "| Metric | Name | Version | Unit | vs. CS Demo Manager |"]
        lines.append("|---|---|---|---|---|")
        for m in metrics:
            lines.append(
                f"| [`{m.id}`]({m.id}.md) | {m.name} | {m.version} | {m.unit} | {_csdm(m.id)} |"
            )
        lines.append("")
    return "\n".join(lines)


def _parameters() -> str:
    used: dict[str, list[str]] = {}
    for m in sorted(REGISTRY.values(), key=lambda m: m.id):
        for key in m.params:
            used.setdefault(key, []).append(m.id)
    lines = ["# Parameters", "", GENERATED, ""]
    lines += [
        "Metric parameters are applied when a metric is computed: "
        '`compute(dataset, params={"trade.window_s": 3.0})`. Derivation parameters are applied '
        "when the round model is built, so changing one means deriving again. Reference "
        "parameters choose the matches of the player's own reference (`untraded.reference`). "
        "🎯 marks a v0 "
        "threshold still to calibrate on demos from consenting high-level players (ADR 0010).",
        "",
        "| Parameter | Default | Unit | Stage | 🎯 | Meaning | Used by |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in sorted(PARAMETERS.values(), key=lambda p: p.id):
        fallback = "the self reference" if p.stage == "reference" else "the round model"
        metrics = ", ".join(f"[`{i}`]({i}.md)" for i in used.get(p.id, [])) or fallback
        lines.append(
            f"| `{p.id}` | {json.dumps(p.default)} | {p.unit} | {p.stage} | "
            f"{'🎯' if p.calibrate else ''} | {p.doc} | {metrics} |"
        )
    return "\n".join([*lines, ""])


def _page(m: Metric, example: str, where: str) -> str:
    source = Path(inspect.getsourcefile(m.compute) or "")
    module = source.relative_to(Path(untraded.__file__).parent).as_posix()
    function = m.compute.__name__
    lines = [f"# `{m.id}`: {m.name}", "", GENERATED, ""]
    lines += [
        "| Version | Kind | Unit | Reads | Code |",
        "|---|---|---|---|---|",
        f"| {m.version} | {m.kind} | {m.unit} | {', '.join(f'`{t}`' for t in m.uses) or '—'} "
        f"| [`{function}` in `{module}`]({CODE}/{module}) |",
        "",
        "## Definition",
        "",
        m.doc,
        "",
    ]
    if m.params:
        lines += ["## Parameters", "", "| Parameter | Default | Meaning |", "|---|---|---|"]
        for key, default in m.params.items():
            p = PARAMETERS[key]
            mark = " 🎯 v0, to calibrate." if p.calibrate else ""
            unit = "" if isinstance(default, bool) else f" {p.unit}"
            lines.append(f"| `{key}` | {json.dumps(default)}{unit} | {p.doc}{mark} |")
        lines.append("")
    lines += ["## Example", "", f"On {where}.", "", example, ""]
    lines += ["## Against CS Demo Manager", "", _csdm_detail(m.id), ""]
    family = m.id.split(".")[0]
    limits = [*LIMITS.get(m.id, ()), *FAMILY_LIMITS.get(family, ())]
    shared = "See also the [shared conventions](README.md#shared-conventions) of every metric."
    lines += ["## Limits", "", *(f"- {limit}" for limit in limits), "", shared, ""]
    lines += ["## History", "", *(f"- **{v}**: {c}" for v, c in history(m.id, m.version)), ""]
    return "\n".join(lines)


def _value_example(rows: pl.DataFrame, names: Mapping[int, str], m: Metric) -> str:
    cells = [(names[r["steamid"]], _fmt(r["value"])) for r in rows.iter_rows(named=True)]
    header = "| " + " | ".join(n for n, _ in cells) + " |"
    return "\n".join(
        [header, "|" + "---|" * len(cells), "| " + " | ".join(v for _, v in cells) + " |"]
    )


def _table_example(frame: pl.DataFrame, names: Mapping[int, str]) -> str:
    frame = frame.drop("metric", "version", "params", "match_id", strict=False)
    if "steamid" in frame.columns:
        frame = frame.with_columns(
            pl.col("steamid").replace_strict(names, return_dtype=pl.String).alias("player")
        ).select("player", pl.exclude("steamid", "player"))
    if frame.height == 0:
        return "*No rows on this window: the thresholds need more rounds.*"
    frame = frame.sort(frame.columns)
    shown = frame.head(TABLE_ROWS)
    lines = ["| " + " | ".join(shown.columns) + " |", "|" + "---|" * shown.width]
    lines += ["| " + " | ".join(_fmt(v) for v in row) + " |" for row in shown.iter_rows()]
    if frame.height > TABLE_ROWS:
        lines += ["", f"*First {TABLE_ROWS} of {frame.height} rows.*"]
    return "\n".join(lines)


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return "—" if math.isnan(value) else f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _csdm(metric_id: str) -> str:
    """The rule a comparison is held to, not its outcome: gaps remain, each one explained."""
    if metric_id in COMPARED:
        return "compared (equal)" if COMPARED[metric_id] == "exact" else "compared (1 %)"
    return "indirectly" if metric_id in COMPARED_TOO else "—"


def _csdm_detail(metric_id: str) -> str:
    report = "[validation-csdm.md](../validation-csdm.md)"
    if metric_id in COMPARED:
        rule = "equal values" if COMPARED[metric_id] == "exact" else "a 1 % tolerance"
        return (
            f"Compared player by player on 30 matches, against {rule}. The values that differ "
            f"are counted and explained, each by a documented definition difference, in {report}."
        )
    if metric_id in COMPARED_TOO:
        return (
            f"No field of its own in CS Demo Manager; compared {COMPARED_TOO[metric_id]}: "
            f"see {report}."
        )
    return "No equivalent in CS Demo Manager."


def write(directory: Path = DOCS) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    pages = render()
    for stale in directory.glob("*.md"):
        if stale.name not in pages:
            stale.unlink()
    for name, text in pages.items():
        (directory / name).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write(Path(sys.argv[1]) if len(sys.argv) > 1 else DOCS)
