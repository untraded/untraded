# 0008. Rounds from game state, events as optional input

- Status: Accepted
- Date: 2026-10-14
- Refines: [0002](0002-parser-agnostic-canonical-tables.md)

## Context

ADR 0002 assumed demos carry the round and purchase events that metric tools usually rely on. Phase 0 (spikes S0.2 and S0.4, 41 demos: Premier, FACEIT, LAN and online tournaments) showed otherwise:

- `round_start`, `round_end`, `item_purchase` and `bullet_impact` exist in **no** CS2 demo.
- `round_officially_ended` and `player_blind` **depend on the server**: present in matchmaking, FACEIT and one online-qualifier server, absent from 11 of 12 tournament demos. Only `round_freeze_end` exists everywhere.
- Some organizer demos **start in the middle of round 1**, or contain an extra freeze end **during warmup** or **before any player is in game**. Only LAN demos had exactly one freeze end per round played.
- The header carries neither the **tickrate** nor the **game mode**. `aim_punch_angle` disappeared from demos after the 2026-09-09 update; `inaccuracy` and `usercmd_subtick_moves` never exist.
- The game rules entity is reliable everywhere: `total_rounds_played`, `is_warmup_period`, `team_rounds_total`, `round_win_status` (winning side) and `round_win_reason` (bomb exploded, defused, elimination, time).

## Decision

1. **Rounds come from game state, not events.** A round starts at a freeze end that is live: not in warmup, with players in game. It is numbered from `total_rounds_played`. It ends when `total_rounds_played` increments. The winner comes from `round_win_status`, the reason from `round_win_reason` (mapped to canonical names), and the score from `team_rounds_total`.
2. **Events are optional input.** The adapter lists the events of each demo (`list_game_events`), and the `match` table records which ones were present. A canonical table whose source event is missing is either **rebuilt by a documented fallback** or **marked unavailable** for that match. It is never left silently empty.
3. **Fallbacks:**
   - **blinds** come from rises of the `flash_duration` prop right after a `flashbang_detonate`, attributed to the thrower;
   - **purchases** come from changes in `inventory` and `balance` during buy time;
   - **round end, winner and reason** come from game state (point 1).
4. **Truncated demos are accepted and flagged.** If the first live round is not round 1, the missing rounds are recorded as missing, the match is flagged `incomplete_start`, and per-round metrics skip those rounds. Totals that need them (e.g. the final score) still come from game state.
5. **The tickrate is computed from the demo** (ticks against elapsed game time), never assumed and never read from the header.
6. **The game mode is an input**, given by the ingestion source (Game Coordinator, FACEIT, upload form), since the demo does not carry it. Unsupported modes (e.g. Wingman) are filtered before parsing.
7. No metric uses `aim_punch_angle`, `inaccuracy`, `usercmd_subtick_moves` or `bullet_impact`. Impacts on players come from `player_hurt`, shots from `weapon_fire`.

## Consequences

- The adapter is more complex than reading events, but behaves the same on every server we have seen.
- The spike check becomes a test: live freeze ends = rounds played = final score, on fixtures that include a truncated online demo.
- Metrics must handle a missing table (e.g. no purchases, if inventory is unreadable) explicitly, and say so in their output.
- Any new event or prop a metric depends on must first be checked on the corpus, across servers.
