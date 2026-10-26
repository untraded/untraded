# Roadmap

Untraded moves phase by phase; a phase opens only when the previous one meets its exit criterion.

| Phase | Scope | Exit criterion |
|---|---|---|
| **0. De-risking** ✓ *done 2026-10-14* | Spikes: Valve pipeline (share codes → Game Coordinator → demo), demo parsing cost and content, FACEIT browser extension, pro demo sources, scrim uploads (MatchZy), storage and compute costs | 10 consecutive Premier matches fetched unattended; one FACEIT demo received through the extension prototype; costs measured |
| **1. Metrics engine** ✓ *done 2026-10-20* | `untraded` Python library and CLI: canonical tables, duels and trades, positioning, utility, economy, HLTV 1.0 and 2.0 (approx.), personal 30-day baselines, generated metric docs | ≤ 1 % deviation from CS Demo Manager on shared stats over 20 matches (met on 30, every gap explained: [validation-csdm.md](validation-csdm.md)) |
| **2. Solo beta** ← *now* | Collector (Valve, Renown), FACEIT extension, worker, API, web app (session report, match page, trends), open win-probability rating v1, rule-based advice with adjustable tone, Discord bot, PWA, exports | 98 % of matches processed without error; 5 weekly active high-level testers; ≥ 60 % of advice rated useful |
| **3. Team beta** | Team workspaces, configurable permissions, roster and stand-ins, scrim webhook, tactical team stats, rich 2D round viewer, review playlists and comments, opt-in public profiles | 2–3 semi-pro teams use it for their weekly review for a month |
| **4. Hosted version** | Bot pool, adaptive polling, rank-based benchmarks, backups, observability | — |
| **5. Later** | Pattern detection, true line of sight, aim level 2, optional LLM summaries grounded in computed evidence, scouting, public API and plugins | — |

## Phase 2 so far

Delivered:

- **Valve collector** (`apps/collector`): follows players' Premier matches through their share-code chain and a Game Coordinator bot, and queues the demos.
- **Demo uploads**: players send FACEIT, ESEA and scrim demos from the site; Valve demos are recognised as Premier. A demo the sender did not play in is refused.
- **Worker** (`apps/worker`): download, upload checks, parsing, play sessions and their reports, advice, round replays, swings, references by level, raw demo retention, erasure on request.
- **API** (`apps/api`, FastAPI): Steam sign-in by invitation, under row-level security; matches, sessions, replays, uploads, consent, erasure, admin.
- **Web app** (`apps/web`, Next.js, English and French): home page, matches, match page, 2D round viewer (our own radars, the round's win-probability curve and swings), session reports with priorities and follow-up, progress page, formulas pages, demo upload, settings (language, coach or analyst tone, consent, erasure), onboarding and admin.
- **Rule-based advice** (`untraded.advice`, [advice.md](advice.md)): 10 open rules, up to three priorities per session with evidence rounds, actions and feedback, followed from one session to the next.
- **Open win-probability model** v1 (`untraded.winprob`, [winprob.md](winprob.md)), each action's swing and the `rating.swing` metric.
- **Self-hosting** with Docker Compose ([self-hosting.md](self-hosting.md)), with a daily database dump.

Still to come in phase 2: the open rating on its 1.00 scale, Renown, the FACEIT extension (the [S0.3](../spikes/S0.3-faceit-extension/) prototype is not part of the product yet), the Discord bot, the PWA and exports.

Metric definitions for phase 1: [metrics-v1.md](metrics-v1.md). Architecture decisions: [adr/](adr/).
