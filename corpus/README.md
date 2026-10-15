# Demo corpus

Reference demos used for regression tests, cross-validation against CS Demo Manager, and calibration (ADR 0010).

- `manifest.toml` lists every demo: id, source, map, date, sha256 and size of the decompressed demo, stored format, game build.
- The files live **outside git**, in `$UNTRADED_CORPUS_DIR/demos/<sha256><stored_as>`, and in a private shared store. Compressed demos are kept as received (`.dem.bz2` from Valve, `.dem.zst` from FACEIT); a plain `.dem` is compressed once with zstd (ADR 0009).
- Demos contain every player's identity: **no corpus demo is public**. Pro demos are for internal engineering only and nothing derived from them is published (ADR 0010).
- Valve demos expire about 30 days after the match: add useful ones to the corpus as soon as they are fetched.
- Phase 1 target: about 40 demos (20 Premier, 8 FACEIT, 4 scrims, the pro demos already collected), covering the active map pool, demos before and after the 2026-09-09 patch, and at least one overtime.

## Commands

```bash
export UNTRADED_CORPUS_DIR=~/untraded-corpus
untraded corpus add ~/Downloads/*.dem.zst --source faceit --played-at 2026-10-14
untraded corpus list
untraded corpus verify          # re-hashes every file; --quick checks presence only
```

`--source` is one of `valve-premier`, `faceit`, `esea`, `scrim`, `pro`. The demo does not carry its date nor its game mode: pass `--played-at` when known, and only add supported modes (no Wingman). Run the commands from the repository root (or pass `--manifest`), then commit `manifest.toml`.
