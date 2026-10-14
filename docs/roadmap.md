# Roadmap

Untraded moves phase by phase; a phase opens only when the previous one meets its exit criterion.

| Phase | Scope | Exit criterion |
|---|---|---|
| **0. De-risking** ✓ *done 2026-10-14* | Spikes: Valve pipeline (share codes → Game Coordinator → demo), demo parsing cost and content, FACEIT browser extension, pro demo sources, scrim uploads (MatchZy), storage and compute costs | 10 consecutive Premier matches fetched unattended; one FACEIT demo received through the extension prototype; costs measured |
| **1. Metrics engine** ← *now* | `untraded` Python library and CLI: canonical tables, duels and trades, positioning, utility, economy, HLTV 1.0 and 2.0 (approx.), personal 30-day baselines, generated metric docs | ≤ 1 % deviation from CS Demo Manager on shared stats over 20 matches |
| **2. Solo beta** | Collector (Valve, Renown), FACEIT extension, worker, API, web app (session report, match page, trends), open win-probability rating v1, rule-based advice with adjustable tone, Discord bot, PWA, exports | 98 % of matches processed without error; 5 weekly active high-level testers; ≥ 60 % of advice rated useful |
| **3. Team beta** | Team workspaces, configurable permissions, roster and stand-ins, scrim webhook, tactical team stats, rich 2D round viewer, review playlists and comments, opt-in public profiles | 2–3 semi-pro teams use it for their weekly review for a month |
| **4. Hosted version** | Bot pool, adaptive polling, rank-based benchmarks, backups, observability | — |
| **5. Later** | Pattern detection, true line of sight, aim level 2, optional LLM summaries grounded in computed evidence, scouting, public API and plugins | — |

Metric definitions for phase 1: [metrics-v1.md](metrics-v1.md). Architecture decisions: [adr/](adr/).
