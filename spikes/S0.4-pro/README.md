# Spike S0.4 — pro demos

Question: do pro demos (tournament servers, GOTV broadcast) parse like matchmaking demos, and can rounds be cut reliably in them?

```bash
just spike-parsing /path/to/pro/demos   # timings, RAM, events and props (S0.2 script)
just spike-rounds /path/to/pro/demos    # round cutting, warmup, flash data
```

`spike-rounds` reads `.dem` files only (extract the archives first). It prints one line per demo: freeze ends vs. rounds played and final score, the first live round, freeze ends during warmup, and how many players `flash_duration` marks as blinded after each flashbang. Findings go to `RAPPORT.md`.

Demos used for this spike are kept locally for internal testing and are never redistributed.
