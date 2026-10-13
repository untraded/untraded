# Spike S0.2 — parsing cost and demo content

Question: does demoparser2 fit our budget (< 60 s and < 3 GB per demo), and which events and properties do our demos actually contain?

```bash
just spike-parsing /path/to/demos
```

Accepts `.dem`, `.dem.bz2`, `.dem.zst` and `.dem.gz`. Each demo is analyzed in a fresh process (so peak memory is per demo): header, available and missing events, event counts, full-rate and 16 Hz tick parses with timings and Parquet sizes, and a probe of every property we plan to use (including usercmd). Results go to `out/report.json` and `out/report.md`; findings to `RAPPORT.md`.
