# Demo corpus

Reference demos used for regression tests, cross-validation against CS Demo Manager, and pro baselines.

- `manifest.toml` lists every demo (source, map, date, sha256, size, game build, visibility).
- The files live **outside git** in `$UNTRADED_CORPUS_DIR`, stored as `<sha256>.dem.zst`.
- Matchmaking, FACEIT and scrim demos contain other players' identities: they stay **private**. Only pro demos may be shared.
- Valve demos expire about 30 days after the match: copy useful ones into the corpus as soon as they are fetched.
- Phase 1 target: about 40 demos (20 Premier, 8 FACEIT, 4 scrims, 10+ pro), covering the active map pool, demos before and after the 2026-09-09 patch, and at least one overtime.

Tooling (`untraded corpus add | verify | list`) arrives with phase 1, workstream E2.
