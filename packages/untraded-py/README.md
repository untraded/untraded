# untraded

Open, transparent Counter-Strike 2 match metrics.

The metrics engine of [Untraded](https://github.com/untraded/untraded), a self-hostable CS2 demo analyzer and coach. It turns a demo into canonical tables, a round model and **81 versioned metrics**: base stats, duels and trades, positioning, utility, economy, HLTV 1.0 and an approximation of HLTV 2.0. Every metric ships with its formula, its parameters, its version and its tests ([metric pages](https://github.com/untraded/untraded/tree/main/docs/metrics)), and the shared stats are checked against CS Demo Manager on 30 matches ([report](https://github.com/untraded/untraded/blob/main/docs/validation-csdm.md)).

> **Alpha.** The library and the command line are usable now; the web app comes later. Metric versions follow semver, but the Python API may still change before 1.0.

## Command line

```bash
untraded analyze match.dem.zst --mode premier              # terminal report
untraded analyze match.dem.zst --mode premier --side CT    # CT rounds only
untraded analyze match.dem.zst --mode premier --format json > report.json
untraded analyze match.dem.zst --mode premier --out out/   # also writes Parquet
```

The report lists every player's main stats (K, D, A, ADR, HS %, KAST, opening kills, untraded deaths, HLTV 1.0 and an approximation of HLTV 2.0), the same per side, and the key rounds: multi-kills, won clutches, eco or force rounds won against a full buy. The JSON output holds every metric of the registry, with its version. `--out` writes the canonical tables, the round model and the metrics as Parquet.

Demos can be `.dem`, `.dem.bz2`, `.dem.gz` or `.dem.zst`. The modes are `premier`, `faceit`, `esea`, `scrim` and `pro`.

Several matches:

```bash
untraded parse demos/*.dem.bz2 --mode premier --out parsed/     # in parallel, as the free RAM allows
untraded reference parsed/matches/* --player 7656119... --session <match id>
```

`untraded parse` takes many demos at once and adapts to the machine (low priority, a demo starts when the free RAM covers it). `untraded reference` compares a session with the player's own 30 days before it, recomputed over all the rounds, and shown from 5 matches and 100 rounds. `untraded calibrate` measures the adjustable thresholds on a corpus ([method](https://github.com/untraded/untraded/blob/main/docs/calibration.md)).

`untraded compare-csdm` checks our stats against CS Demo Manager's analyzer (see `docs/validation-csdm.md`).

`untraded fixture extract match.dem.zst --mode premier --rounds 11-15 --name my-bug --out my-bug/` writes an anonymized extract of a few rounds: steamids, names, server, teams, date and rank are removed. It is enough to reproduce most metric issues, so you can attach it to a bug report instead of your demo.

## Library

```python
from pathlib import Path

from untraded.derive import derive
from untraded.metrics import Dataset, compute
from untraded.parsing import parse_demo

match = parse_demo(Path("match.dem.zst"), source="upload", mode="premier")
tables = match.tables()
ds = Dataset.from_matches([{**tables, **derive(tables).tables()}])
compute(ds)                                       # every value metric, per player
compute(ds.split(side="CT"), ["base.kast"])       # one metric, CT rounds only
compute(ds, params={"trade.window_s": 3.0})       # another trade window
```

Results record each metric's version and the parameters used. The ratings are also available on match totals:

```python
from untraded import rating_hltv_1

rating_hltv_1(rounds=24, kills=25, deaths=15, multikills={1: 10, 2: 4, 3: 1, 4: 1})
```

`rating_hltv_1` implements HLTV's public Rating 1.0 formula:

```
(KillRating + 0.7 × SurvivalRating + MultiKillRating) / 2.7

KillRating      = (kills / rounds) / 0.679
SurvivalRating  = ((rounds − deaths) / rounds) / 0.317
MultiKillRating = ((1K + 4×2K + 9×3K + 16×4K + 25×5K) / rounds) / 1.277
```

`rating_hltv_2_approx` is a community approximation of Rating 2.0, whose formula HLTV does not publish: always present it as "approx.".

Untraded is not affiliated with HLTV or Valve.

## License

MIT
