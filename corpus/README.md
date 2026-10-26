# Demo corpus

Reference demos used for regression tests, cross-validation against CS Demo Manager, calibration (ADR 0010) and training the win-probability model ([docs/winprob.md](../docs/winprob.md); never on pro demos).

- `manifest.toml` lists every demo: id, source, map, date, sha256 and size of the decompressed demo, stored format, game build.
- The files live **outside git**, in `$UNTRADED_CORPUS_DIR/demos/<sha256><stored_as>`, and in a private shared store. Compressed demos are kept as received (`.dem.bz2` from Valve, `.dem.zst` from FACEIT); a plain `.dem` is compressed once with zstd (ADR 0009).
- Demos contain every player's identity: **no corpus demo is public**. Pro demos are for internal engineering only and nothing derived from them is published (ADR 0010).
- Valve demos expire about 30 days after the match: add useful ones to the corpus as soon as they are fetched.
- Phase 1 aimed at about 40 demos (20 Premier, 8 FACEIT, 4 scrims, the pro demos already collected), covering the active map pool, demos before and after the 2026-09-09 patch, and at least one overtime. The manifest now lists 43: 29 Premier, 2 FACEIT and 12 pro demos; ESEA and scrim demos are still missing.

## Commands

```bash
export UNTRADED_CORPUS_DIR=~/untraded-corpus
untraded corpus add ~/Downloads/*.dem.zst --source faceit --played-at 2026-10-14
untraded corpus list
untraded corpus verify          # re-hashes every file; --quick checks presence only

export UNTRADED_CORPUS_REMOTE=untraded-corpus:corpus/demos
untraded corpus push            # upload what the shared store lacks (files are re-hashed first)
untraded corpus pull            # download what is missing locally (each file is checked)
```

`pull` and `push` use the OpenSSH `sftp` client (Linux, macOS and Windows) with a host alias from `~/.ssh/config`: the access key stays in your SSH configuration, never in the repository. Both accept `--dry-run`.

`--source` is one of `valve-premier`, `faceit`, `esea`, `scrim`, `pro`. The demo does not carry its date nor its game mode: pass `--played-at` when known, and only add supported modes (no Competitive, no Wingman). Run the commands from the repository root (or pass `--manifest`), then commit `manifest.toml`.
