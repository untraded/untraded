# Spikes (phase 0)

Throwaway experiments that answered one risky question each. Phase 0 closed on 2026-10-14; the product code is in `apps/` and `packages/`. Code here is not production code: it is linted but not held to the strict typing bar. Each spike ends with a `RAPPORT.md` (maintainer notes, in French) and a go/no-go decision.

| Spike | Question | Status |
|---|---|---|
| [S0.1-valve](S0.1-valve/) | Share code → Game Coordinator → demo, unattended, for a week? | Done (provisional GO; continued as `apps/collector`) |
| [S0.2-parsing](S0.2-parsing/) | What do demos contain, and what does parsing cost? | Done (GO) |
| [S0.3-faceit-extension](S0.3-faceit-extension/) | Can an extension send a FACEIT demo from the match room? | Done (GO for self-hosting) |
| [S0.4-pro](S0.4-pro/) | Which pro demo source can we use, and do pro demos parse like MM demos? | Done (technical GO, source open) |
| S0.5-matchzy | Does a MatchZy scrim server upload demos to our endpoint? | Not run (optional) |
| [S0.6-costs](S0.6-costs/) | Storage and CPU per match, projected hosting cost | Done (GO; Premier demos measured on ARM and x86) |
