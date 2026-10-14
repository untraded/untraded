# Spike S0.6 — storage and CPU per match

Question: how much disk and CPU does one match cost, so that hosting can be sized and priced?

```bash
just spike-costs /path/to/demos [/another/dir ...]
```

Accepts `.dem`, `.dem.bz2`, `.dem.zst` and `.dem.gz`. Each demo runs in a fresh process and is measured three ways:

- decompressing the source file;
- re-compressing the `.dem` with zstd at levels 1, 3 and 9 (level 19 was tried once: about 10 % smaller than level 9 for ~170 CPU seconds per demo, out of budget);
- what the worker will do: parse the key events and 24 props at 16 Hz, and write them as Parquet (zstd).

Times are **CPU seconds** (user + system, all threads), not wall time: demoparser2 is multi-threaded, so wall time on a many-core machine hides the real cost. Results go to `out/costs.json` (ignored by Git) and a summary to the console; findings to `RAPPORT.md`.
