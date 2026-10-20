# untraded

Open, transparent Counter-Strike 2 match metrics.

> **Early preview.** This package will host the open metrics library of [Untraded](https://github.com/untraded), a self-hostable CS2 demo analyzer and coach. Every metric ships with its formula, its version and its tests.

## Command line

```bash
untraded analyze match.dem.zst --mode premier              # terminal report
untraded analyze match.dem.zst --mode premier --side CT    # CT rounds only
untraded analyze match.dem.zst --mode premier --format json > report.json
untraded analyze match.dem.zst --mode premier --out out/   # also writes Parquet
```

The report lists every player's main stats (K, D, A, ADR, HS %, KAST, opening kills, untraded deaths, HLTV 1.0 and an approximation of HLTV 2.0), the same per side, and the key rounds: multi-kills, won clutches, eco or force rounds won against a full buy. The JSON output holds every metric of the registry, with its version. `--out` writes the canonical tables, the round model and the metrics as Parquet.

Demos can be `.dem`, `.dem.bz2`, `.dem.gz` or `.dem.zst`. The modes are `premier`, `faceit`, `esea`, `scrim` and `pro`.

`untraded compare-csdm` checks our stats against CS Demo Manager's analyzer (see `docs/validation-csdm.md`).

`untraded fixture extract match.dem.zst --mode premier --rounds 11-15 --name my-bug --out my-bug/` writes an anonymized extract of a few rounds: steamids, names, server, teams, date and rank are removed. It is enough to reproduce most metric issues, so you can attach it to a bug report instead of your demo.

## Library

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
