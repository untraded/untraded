# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""A mock of the Untraded API, to work on the web app without a database or demos.

    uv run python apps/web/dev/mock_api.py           # http://127.0.0.1:8077
    UNTRADED_API_INTERNAL_URL=http://127.0.0.1:8077 pnpm --filter @untraded/web dev

Everything is invented (players, scores, metrics) and seeded, so screens look the same from one
run to the next. It answers like `apps/api` (same JSON shapes, see `apps/web/src/lib/api.ts`):
- signing in: `/api/auth/steam` sets the session cookie and goes back to the web (no Steam);
- sessions cover the three references (own days, level, none), priorities with evidence,
  👍/👎 (kept in memory), and the follow-up of the previous priorities;
- matches cover every status (ready, analysing, unavailable...);
- onboarding (consent, then the two codes) and the admin, with players in every state;
- round replays for the 2D viewer, from the `premier-half` fixture (see `fixture_replays`).

The signed-in player starts followed and admin. `/api/mock/state/<state>` switches them, to see
each screen: `joined`, `consented`, `followed`, `error` (Valve refuses their code), `withdrawn`,
`outdated` (a newer consent text), `nokey` (the server cannot keep codes), `player` (not admin).
Codes that answer like Steam would: the auth code `XXXX-XXXXX-XXXX` is refused (Steam's 403,
a 422 on `auth_code`), the share code `CSGO-00000-00000-00000-00000-00000` too (Steam's 412),
and `STEA-MDOWN-0503` stands for Steam not answering (503). As in the API, codes are found in
what is pasted, and two codes pasted the other way round are put back in place.
Erasure: `POST /me/erase` signs the player out (signing in again starts afresh), and erasing a
player from the admin removes them from the list (409 for the admin themself).

Metric names, units and directions come from the `untraded` registry when it is installed
(`uv run`), so the mock stays in step with the real metrics.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = int(os.environ.get("MOCK_PORT", "8077"))
WEB = os.environ.get("MOCK_WEB_URL", "http://localhost:3000").rstrip("/")
COOKIE = "untraded_session"
ME = "76561190000000001"
NAMES = ["you", "Kestrel", "Brindle", "Oxide", "Tamsin", "Vireo", "Quill", "Marlow", "Juno", "Pike"]
MAPS = ["de_mirage", "de_ancient", "de_inferno", "de_nuke", "de_dust2", "de_anubis", "de_train"]
# The latest match an hour ago, so the lists show today, yesterday, this week… as the site sees them.
NOW = dt.datetime.now(dt.UTC).replace(minute=0, second=0, microsecond=0)
rand = random.Random(7)


def iso(moment: dt.datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def mock_id(prefix: int, n: int) -> str:
    return str(uuid.UUID(int=(prefix << 64) + n))


def metrics() -> list[dict[str, str]]:
    try:
        from untraded.metrics import REGISTRY

        return [
            {
                "id": m.id,
                "version": m.version,
                "name": m.name,
                "unit": m.unit,
                "better": m.better,
                "cases": list(m.cases),
                "signed": m.signed,
            }
            for m in REGISTRY.values()
            if m.kind == "value"
        ]
    except ImportError:  # outside the uv workspace: a few metrics are enough
        return [
            {"id": "rating.untraded", "version": "1.0.0", "name": "Untraded Rating", "unit": "ratio", "better": "higher", "cases": ["rounds"], "signed": False},
            {"id": "rating.hltv1", "version": "1.0.0", "name": "HLTV Rating 1.0", "unit": "ratio", "better": "higher", "cases": ["rounds"], "signed": False},
            {"id": "base.adr", "version": "1.0.0", "name": "ADR", "unit": "damage_per_round", "better": "higher", "cases": ["rounds"], "signed": False},
            {"id": "base.kast", "version": "1.1.0", "name": "KAST", "unit": "pct", "better": "higher", "cases": ["rounds"], "signed": False},
            {"id": "trade.untraded_deaths", "version": "1.1.0", "name": "Untraded deaths (5 s)", "unit": "count", "better": "lower", "cases": [], "signed": False},
            {"id": "base.kills", "version": "1.0.0", "name": "Kills", "unit": "count", "better": "higher", "cases": [], "signed": False},
        ]  # fmt: skip


METRICS = metrics()
TOTALS = {"count", "hp"}


def line() -> dict[str, float]:
    kills, deaths = rand.randint(9, 28), rand.randint(10, 22)
    return {
        "kills": kills,
        "deaths": deaths,
        "adr": round(rand.uniform(55, 112), 1),
        "kast": round(rand.uniform(55, 86), 1),
        "hltv1": (hltv1 := round(rand.uniform(0.7, 1.45), 2)),
        "untraded_deaths": rand.randint(1, 9),
        "untraded": round(hltv1 * rand.uniform(0.85, 1.15), 2),
    }


def build_matches() -> list[dict[str, Any]]:
    statuses = ["parsing"] + ["ready"] * 11 + ["unavailable", "failed"] + ["ready"] * 36
    found = []
    for n, status in enumerate(statuses):
        # Every 9 hours, then about one every 2.5 days: older matches reach back over 3 months.
        start = NOW - dt.timedelta(hours=1 + n * 9 + max(0, n - 7) * 60)
        ready = status == "ready"
        a, b = (13, rand.randint(4, 11)) if n % 3 else (rand.randint(5, 12), 13)
        team = "A" if n % 2 else "B"
        mine, theirs = (a, b) if team == "A" else (b, a)
        found.append(
            {
                "id": mock_id(1, n),
                "played_at": iso(start),
                "ended_at": iso(start + dt.timedelta(minutes=38)),
                "mode": "premier",
                "status": status,
                "map": MAPS[n % len(MAPS)],
                "score_a": a if ready else None,
                "score_b": b if ready else None,
                "rounds_played": a + b if ready else None,
                "my_team": team,
                "my_result": ("win" if mine > theirs else "loss") if ready else None,
                "my_line": line() if ready else None,
            }
        )
    return found


MATCHES = build_matches()


def match_detail(match: dict[str, Any]) -> dict[str, Any]:
    ready = match["status"] == "ready"
    rounds, a, b = [], 0, 0
    for r in range(1, (match["rounds_played"] or 0) + 1):
        left_a, left_b = match["score_a"] - a, match["score_b"] - b
        winner = "A" if rand.random() < left_a / (left_a + left_b) else "B"
        a, b = a + (winner == "A"), b + (winner == "B")
        ct = "A" if r <= 12 else "B"
        rounds.append(
            {
                "round": r,
                "winner_side": "CT" if winner == ct else "T",
                "winner_team": winner,
                "reason": rand.choice(["elimination", "bomb_exploded", "bomb_defused", "time_ran_out"]),
                "ct_team": ct,
                "score_a": a,
                "score_b": b,
                "is_overtime": False,
                "bomb_site": rand.choice(["A", "B", None]),
                "bomb_planted": rand.random() < 0.4,
            }
        )  # fmt: skip
    players = [
        {
            "steam_id": ME if i == 0 else str(76561190000000100 + i),
            "name": NAMES[i],
            "team": match["my_team"] if i < 5 else ("B" if match["my_team"] == "A" else "A"),
            "rank": rand.randint(15000, 21000),
            "rounds_on_team": match["rounds_played"],
            "line": match["my_line"] if i == 0 else line(),
        }
        for i in range(10)
    ]
    errors = {
        "unavailable": "not a Premier match: rank type 12 (Competitive)",
        "failed": "demo is truncated",
    }
    return match | {
        "team_a_name": None,
        "team_b_name": None,
        "tickrate": 64.0,
        "unavailable": [],
        "error": errors.get(match["status"]),
        "rounds": rounds if ready else [],
        "players": players if ready else [],
    }


def comparison(m: dict[str, str], enough: bool) -> dict[str, Any]:
    basis = "per_round" if m["unit"] in TOTALS else "value"
    reference = rand.uniform(0.1, 1.4) if basis == "per_round" else rand.uniform(5, 90)
    session = reference * rand.uniform(0.75, 1.25)
    return {
        "metric_id": m["id"],
        "version": m["version"],
        "name": m["name"],
        "unit": m["unit"],
        "better": m["better"],
        "basis": basis,
        "session": round(session, 4),
        "reference": round(reference, 4) if enough else None,
        "delta": round(session - reference, 4) if enough else None,
        "signed": m["signed"],
    }


# Rates that rest on few cases in every session: under 5 (a clutch rate over 2 clutches, an opening
# conversion over 1 opening kill) they are left out of what stands out; from 5 to 9 (trade
# conversion over 7 chances) they are ranked but say what they stand on.
FEW_CASES = {
    "clutch.win_pct": 2,
    "duel.opening_win_conversion_pct": 1,
    "duel.opening_success_pct": 3,
    "trade.kill_conversion_pct": 7,
}


def with_cases(values: list[dict[str, Any]], rounds: int) -> list[dict[str, Any]]:
    """What each rate or average stands on, as the API computes it: the rounds played, or the sum
    of its count metrics (per round in a session) times the rounds. Null for totals."""
    per_round = {v["metric_id"]: v["session"] for v in values}
    of = {m["id"]: m["cases"] for m in METRICS}
    for value in values:
        metric = of[value["metric_id"]]
        if not metric:
            cases = None
        elif metric == ["rounds"]:
            cases = rounds
        else:
            cases = round(sum(per_round.get(c) or 0 for c in metric) * rounds)
        value["cases"] = FEW_CASES.get(value["metric_id"], cases)
    return values


HEADLINES = ["rating.untraded", "rating.hltv1", "base.adr", "base.kast", "trade.untraded_deaths"]


# Round replays (2D viewer): the five rounds of the `premier-half` fixture (de_cache, rounds 11 to
# 15), built by `untraded.replay` when it is installed (`uv run`), else none (404). Round n of a
# ready match is fixture round n modulo 5, its players renamed as the mock's ("you" is A1). The
# positions are Cache's, so most replays stay on de_cache, with its radar. Matches on Nuke get
# Nuke's transform, with heights moved so that some players stand on its lower level; matches on
# Anubis get no transform (`radar: null`), to see every case.
NUKE = {"pos_x": -3453, "pos_y": 2887, "scale": 7.0, "lower_below": -495}
NUKE_Z = -2150


def fixture_replays() -> list[dict[str, Any]]:
    try:
        from pathlib import Path

        from untraded import fixtures
        from untraded.replay import build_replays
    except ImportError:
        return []
    root = Path(__file__).resolve().parents[3] / "packages" / "untraded-py" / "tests" / "fixtures"
    replays = build_replays(fixtures.read(root / "premier-half"))
    return [replays[n] for n in sorted(replays)]


FIXTURE_REPLAYS = fixture_replays()
REPLAY_NAMES = {
    str(n): (ME if n == 1 else str(76561190000000100 + n - 1), NAMES[n - 1]) for n in range(1, 11)
}


def fixture_round(n: int) -> dict[str, Any] | None:
    return FIXTURE_REPLAYS[(n - 1) % len(FIXTURE_REPLAYS)] if FIXTURE_REPLAYS else None


def replay(match: dict[str, Any], n: int) -> dict[str, Any] | None:
    base = fixture_round(n)
    if base is None:
        return None
    found = json.loads(json.dumps(base))
    rename = lambda sid: REPLAY_NAMES.get(sid, (sid, ""))[0] if sid is not None else None  # noqa: E731
    for player in found["players"]:
        player["steamid"], player["name"] = REPLAY_NAMES[player["steamid"]]
    for kill in found["kills"]:
        for key in ("attacker", "victim", "assister"):
            kill[key] = rename(kill[key])
    for grenade in found["grenades"]:
        grenade["thrower"] = rename(grenade["thrower"])
    for blind in found["blinds"]:
        blind["victim"], blind["flasher"] = rename(blind["victim"]), rename(blind["flasher"])
    for event in found["bomb"]["events"]:
        event["player"] = rename(event["player"])
    for swing in (found.get("winprob") or {}).get("swings", []):
        swing["player"] = rename(swing["player"])
    found.update({"match_id": match["id"], "round": n})
    if n % 9 == 0:  # a round the model does not cover: the viewer draws no curve
        found["winprob"] = None
    if match["map"] == "de_anubis":
        found.update({"map": "de_anubis", "radar": None})
    if match["map"] == "de_nuke":
        found["map"] = "de_nuke"
        found["radar"] = NUKE
        move = lambda z: None if z is None else z + NUKE_Z  # noqa: E731
        for player in found["players"]:
            player["z"] = [move(z) for z in player["z"]]
        for kill in found["kills"]:
            kill["attacker_z"], kill["victim_z"] = move(kill["attacker_z"]), move(kill["victim_z"])
        for grenade in found["grenades"]:
            grenade["path"]["z"] = [move(z) for z in grenade["path"]["z"]]
            if grenade["detonate"]:
                grenade["detonate"][2] = move(grenade["detonate"][2])
        if found["bomb"]["planted_at"]:
            found["bomb"]["planted_at"][2] = move(found["bomb"]["planted_at"][2])
    return found


REPLAY_CACHE: dict[tuple[str, int], bytes] = {}


def replay_gz(match: dict[str, Any], n: int) -> bytes | None:
    """The replay as the API serves it: compact JSON, gzipped."""
    if (match["id"], n) not in REPLAY_CACHE:
        found = replay(match, n)
        if found is None:
            return None
        from untraded.replay import to_json_gz

        REPLAY_CACHE[(match["id"], n)] = to_json_gz(found)
    return REPLAY_CACHE[(match["id"], n)]


def evidence_tick(n: int, i: int) -> int:
    """A kill tick of the replay of round n, so that a round to review opens on its event."""
    base = fixture_round(n)
    if base is None or not base["kills"]:
        return 40_000 + 9_000 * i
    return base["kills"][i % len(base["kills"])]["tick"]


def evidence(match: dict[str, Any], count: int, zone: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "match_id": match["id"],
            "round": 3 + 2 * i,
            "tick": evidence_tick(3 + 2 * i, i),
            "goto_tick": evidence_tick(3 + 2 * i, i) - 320,
            "map": match["map"],
            "side": "T" if i % 2 else "CT",
            "killer": str(76561190000000106),
            **({"zone": zone} if zone else {}),
        }
        for i in range(count)
    ]


# Two evidence matches the API cannot serve, to see the report fall back to a plain list of rounds:
# one is missing (404), the other breaks (500). The session of 19 October points to them.
MISSING_MATCH = mock_id(1, 404)
BROKEN_MATCH = mock_id(1, 500)


def unavailable(
    session_n: int, priority: int, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    target = {2: MISSING_MATCH, 3: BROKEN_MATCH}.get(priority) if session_n == 1 else None
    return [{**event, "match_id": target} for event in events] if target else events


def moments(rule: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Team flashes can blind two teammates in one round: a second moment in the first round, as
    the real rule produces (several events per round)."""
    if rule != "util.team_flashes" or not events:
        return events
    second = {
        **events[0],
        "tick": events[0]["tick"] + 640,
        "goto_tick": events[0]["goto_tick"] + 640,
    }
    return [events[0], second, *events[1:]]


def advice(session_n: int, match: dict[str, Any]) -> list[dict[str, Any]]:
    base = [
        ("trade.untraded_deaths", "trade.untraded_deaths", "count", "per_round", 0.41, 0.29, 9, 7,
         ["adjust.trade_distance", "adjust.play_with_entry", "drill.trade_timing"], {}),
        ("pos.recurring_death_spot", "pos.recurring_death_spot", "table", "pattern", None, None, 4, 4,
         ["adjust.change_position", "adjust.change_timing", "drill.prefire"],
         {"map": match["map"], "side": "T", "zone": "Mid", "history_events": 11}),
        ("util.team_flashes", "util.teammates_flashed", "count", "per_round", 0.18, 0.09, 6, 4,
         ["adjust.call_your_flashes", "drill.pop_flashes"], {}),
    ]  # fmt: skip
    found = []
    for priority, (
        rule,
        metric,
        unit,
        basis,
        session,
        reference,
        events,
        lost,
        actions,
        details,
    ) in enumerate(base, 1):
        indicator = "trade.untraded_deaths" if rule.startswith("pos.") else metric
        found.append(
            {
                "id": mock_id(3, session_n * 10 + priority),
                "rule_id": rule,
                "rule_version": "1.0.0",
                "priority": priority,
                "message_key": f"advice.{rule}",
                "args": {
                    "metric": metric, "unit": unit, "basis": basis, "session": session,
                    "reference": reference, "events": events, "rounds_touched": events,
                    "rounds_lost": lost, "actions": actions, "indicator": indicator, **details,
                },
                "evidence": unavailable(
                    session_n, priority, moments(rule, evidence(match, events, details.get("zone")))
                ),
                "cost": lost + 0.25 * (events - lost),
                "my_vote": VOTES.get(mock_id(3, session_n * 10 + priority)),
            }
        )  # fmt: skip
    return found


VOTES: dict[str, int] = {}
KINDS = ["level", "self", "self", "none", "self", "self"] + ["self"] * 17

# The key figures follow a slow improvement (the newest session first), so the progress page
# draws something readable: (newest value, oldest value, noise, newest reference, oldest one).
HEADLINE_TREND = {
    "rating.untraded": (1.07, 0.93, 0.07, 1.02, 0.97),
    "rating.hltv1": (1.09, 0.92, 0.06, 1.04, 0.96),
    "base.adr": (83.0, 72.0, 5.0, 81.0, 76.0),
    "base.kast": (74.0, 66.0, 3.0, 72.0, 69.0),
    "trade.untraded_deaths": (0.30, 0.46, 0.04, 0.35, 0.41),
}


def headline(value: dict[str, Any], n: int, enough: bool) -> dict[str, Any]:
    """A key figure of session `n` (0 = newest) on its trend, instead of a random draw."""
    trend = HEADLINE_TREND.get(value["metric_id"])
    if trend is None:
        return value
    new, old, noise, ref_new, ref_old = trend
    age = n / (len(KINDS) - 1)
    session = new + (old - new) * age + rand.uniform(-noise, noise)
    reference = ref_new + (ref_old - ref_new) * age
    return value | {
        "session": round(session, 4),
        "reference": round(reference, 4) if enough else None,
        "delta": round(session - reference, 4) if enough else None,
    }


# A session with a reference where no rule fires: the list says nothing stands out.
QUIET = {2}


def session_advice(n: int, session: dict[str, Any]) -> list[dict[str, Any]]:
    if session["_kind"] == "none" or n in QUIET:
        return []
    return advice(n, session["_matches"][0])


def played(match: dict[str, Any]) -> dict[str, Any]:
    """A match of a session, as `GET /sessions` lists it."""
    mine, theirs = (
        (match["score_a"], match["score_b"])
        if match["my_team"] == "A"
        else (match["score_b"], match["score_a"])
    )
    return {
        "match_id": match["id"],
        "map": match["map"],
        "result": match["my_result"],
        "my_score": mine,
        "their_score": theirs,
    }


def build_sessions() -> list[dict[str, Any]]:
    ready = [m for m in MATCHES if m["status"] == "ready"]
    found = []
    for n in range(len(KINDS)):
        group = ready[n * 2 : n * 2 + 2]
        if not group:
            break
        enough = KINDS[n] != "none"
        rounds = sum(m["rounds_played"] for m in group)
        values = with_cases([headline(comparison(m, enough), n, enough) for m in METRICS], rounds)
        wins = sum(m["my_result"] == "win" for m in group)
        found.append(
            {
                "id": mock_id(2, n),
                "started_at": group[-1]["played_at"],
                "ended_at": group[0]["ended_at"],
                "matches": len(group),
                "rounds": rounds,
                "wins": wins,
                "losses": len(group) - wins,
                "ties": 0,
                "enough": enough,
                "headlines": [v for h in HEADLINES for v in values if v["metric_id"] == h],
                "_values": values,
                "_matches": group,
                "_kind": KINDS[n],
            }
        )
    return found


SESSIONS = build_sessions()
PUBLIC = {"_values", "_matches", "_kind"}


def summary(session: dict[str, Any]) -> dict[str, Any]:
    """A session as `GET /sessions` lists it: its matches in the order played, and its first
    priority (null when no rule fired)."""
    n = SESSIONS.index(session)
    first = next(iter(session_advice(n, session)), None)
    top = (
        {
            "rule_id": first["rule_id"],
            "message_key": first["message_key"],
            "args": first["args"],
            "cost": first["cost"],
            "rounds_touched": first["args"]["rounds_touched"],
            "rounds_lost": first["args"]["rounds_lost"],
        }
        if first
        else None
    )
    return {k: v for k, v in session.items() if k not in PUBLIC} | {
        "maps": [played(m) for m in reversed(session["_matches"])],
        "top_priority": top,
    }


def report(n: int) -> dict[str, Any]:
    session = SESSIONS[n]
    kind = session["_kind"]
    previous = SESSIONS[n + 1] if n + 1 < len(SESSIONS) else None
    history = list(reversed(SESSIONS[n : n + 5]))
    follow = []
    if previous is not None:
        for indicator, name, unit, basis, better in [
            ("trade.untraded_deaths", "Untraded deaths (5 s)", "count", "per_round", "lower"),
            ("util.unused_value_at_death", "Wasted utility", "dollars", "value", "lower"),
        ]:
            values = [
                round(rand.uniform(0.25, 0.45), 2)
                if basis == "per_round"
                else float(rand.randint(150, 330))
                for _ in history
            ]
            follow.append(
                {
                    "rule_id": "trade.untraded_deaths" if indicator.startswith("trade") else "util.wasted_utility",
                    "indicator": indicator, "name": name, "unit": unit, "basis": basis, "better": better,
                    "then": values[-2] if len(values) > 1 else None, "now": values[-1],
                    "reference": 0.29 if basis == "per_round" else 180.0,
                    "history": [{"session_id": s["id"], "started_at": s["started_at"], "value": v} for s, v in zip(history, values, strict=True)],
                }
            )  # fmt: skip
    return summary(session) | {
        "reference": {
            "kind": kind,
            "level_low": 15000 if kind == "level" else None,
            "level_high": 22500 if kind == "level" else None,
            "since": "2026-09-20",
            "until": "2026-10-19",
            "matches": {"self": 14, "level": 812, "none": 2}[kind],
            "rounds": {"self": 310, "level": 17000, "none": 41}[kind],
            "enough": kind != "none",
            "min_matches": 5,
            "min_rounds": 100,
        },
        "match_list": session["_matches"],
        "metrics": session["_values"],
        "advice": session_advice(n, session),
        "follow_up": follow,
    }


# The numbers the match page splits by side, drawn within plausible bounds (per side: ~12 rounds).
SIDE_VALUES = {
    "base.kills": (4, 16), "base.deaths": (5, 13), "base.adr": (45, 105), "base.kast": (55, 88),
    "trade.untraded_deaths": (0, 5), "duel.opening_kills": (0, 3), "duel.opening_attempts": (3, 6),
    "rating.hltv1": (0.55, 1.45),
}  # fmt: skip


def player_rating(match_id: str, steam_id: str) -> dict[str, Any] | None:
    """`GET /matches/{id}/players/{steam_id}/rating`, as in `apps/api` (#137): the parts add up
    to the rating."""
    match = next((m for m in MATCHES if m["id"] == match_id), None)
    if match is None or match["status"] != "ready":
        return None
    value = match["my_line"]["untraded"] if steam_id == ME else round(rand.uniform(0.7, 1.4), 2)
    kills = round(value * rand.uniform(0.55, 0.75), 2)
    deaths = -round(rand.uniform(0.15, 0.3), 2)
    plants = round(rand.uniform(0.0, 0.06), 2)
    defuses = round(rand.uniform(0.0, 0.04), 2)
    baseline = round(value - kills - deaths - plants - defuses, 2)
    parts = {
        "kills": kills,
        "deaths": deaths,
        "plants": plants,
        "defuses": defuses,
        "baseline": baseline,
    }
    return {
        "value": value,
        "margin": round(rand.uniform(0.11, 0.19), 2),
        "rounds": match["rounds_played"],
        "parts": [{"part": k, "points": v} for k, v in parts.items()],
    }


def player_metrics(match_id: str, steam_id: str) -> dict[str, Any]:
    values = []
    for m in METRICS:
        for scope in ("match", "ct", "t"):
            value = rand.uniform(0.1, 1.4) if m["unit"] in TOTALS else rand.uniform(5, 90)
            if m["id"] in SIDE_VALUES:
                low, high = SIDE_VALUES[m["id"]]
                value = rand.randint(low, high) if isinstance(low, int) else rand.uniform(low, high)
                value *= 2 if scope == "match" and m["unit"] in TOTALS else 1
            values.append({"metric_id": m["id"], "version": m["version"], "name": m["name"], "unit": m["unit"], "better": m["better"], "scope": scope, "value": round(value, 3)})  # fmt: skip
    return {"match_id": match_id, "steam_id": steam_id, "metrics": values}


# Uploads, as in `apps/api` (`uploads.py`). `/mock/uploads/<refusal>` sets why a new demo would be
# refused before it is sent (`off`, `disk_full`, `consent`, `quota`, `busy`, or `none`). A demo is
# processed for 20 s, then its file name decides what became of it: `notademo`, `corrupt`,
# `compet` (Competitive), `notme` (the player is not in it) or `broken` (parsing failed); any
# other name becomes a match.
UPLOAD_MAX = 400 * 1024 * 1024
UPLOAD_SUFFIXES = (".dem.bz2", ".dem.gz", ".dem.zst", ".dem")
UPLOAD_STATUS = {"off": 503, "disk_full": 507, "consent": 409, "quota": 429, "busy": 429}
UPLOAD_OUTCOMES = {
    "notademo": "not_a_demo",
    "corrupt": "corrupt",
    "compet": "unsupported_mode",
    "notme": "not_a_player",
    "broken": "parse_failed",
}
UPLOAD_STATE: dict[str, Any] = {"refusal": None}
PROCESSING = dt.timedelta(seconds=20)


def upload(n: int, outcome: str, mode: str, days: int) -> dict[str, Any]:
    match = MATCHES[1 + n]
    return {
        "upload_id": mock_id(5, n),
        "match_id": match["id"],
        "received_at": iso(NOW - dt.timedelta(days=days)),
        "mode": mode,
        "map": match["map"],
        "played_at": match["played_at"],
        "_outcome": outcome,
        "_ready_at": NOW - dt.timedelta(days=days),
    }


UPLOADS = [
    upload(0, "ready", "faceit", 1),
    upload(1, "not_a_player", "faceit", 2),
    upload(2, "unsupported_mode", "faceit", 3),
    upload(3, "parse_failed", "scrim", 4),
]


def upload_line(item: dict[str, Any]) -> dict[str, Any]:
    line = {k: v for k, v in item.items() if not k.startswith("_")}
    outcome = item["_outcome"]
    if dt.datetime.now(dt.UTC) < item["_ready_at"]:
        return line | {"state": "processing", "reason": None, "map": None}
    if outcome == "ready":
        return line | {"state": "ready", "reason": None}
    state = "failed" if outcome == "parse_failed" else "refused"
    return line | {"state": state, "reason": outcome}


def receive_upload(handler: Handler, query: str) -> None:
    """`POST /uploads`: the checks before the body, then the body read and dropped."""
    args = dict(re.findall(r"([a-z_]+)=([^&]*)", query))
    name = urllib.parse.unquote(args.get("name", ""))
    size = int(handler.headers.get("content-length") or 0)
    refusal = UPLOAD_STATE["refusal"]
    if refusal == "off":
        return handler.reply(503, {"detail": "uploads are off here"})
    if args.get("mode") not in ("faceit", "esea", "scrim"):
        return handler.reply(422, {"detail": {"field": "mode"}})
    try:
        played = dt.datetime.fromisoformat(urllib.parse.unquote(args.get("played_at", "")))
    except ValueError:
        played = None
    if played is None or played.tzinfo is None:
        return handler.reply(422, {"detail": {"field": "played_at"}})
    if refusal:
        return handler.reply(UPLOAD_STATUS[refusal], {"detail": {"reason": refusal}})
    if not name.lower().endswith(UPLOAD_SUFFIXES):
        return handler.reply(422, {"detail": {"reason": "not_a_demo"}})
    if size > UPLOAD_MAX:
        return handler.reply(413, {"detail": {"reason": "too_large"}})
    left = size
    while left > 0:
        chunk = handler.rfile.read(min(left, 1 << 20))
        if not chunk:
            break
        left -= len(chunk)
    outcome = next((o for key, o in UPLOAD_OUTCOMES.items() if key in name.lower()), "ready")
    n = len(UPLOADS)
    match = MATCHES[1 + n % 10]
    item = {
        "upload_id": mock_id(5, n),
        "match_id": match["id"],
        "received_at": iso(dt.datetime.now(dt.UTC)),
        "mode": args["mode"],
        "map": match["map"],
        "played_at": played.astimezone(dt.UTC).isoformat().replace("+00:00", "Z"),
        "_outcome": outcome,
        "_ready_at": dt.datetime.now(dt.UTC) + PROCESSING,
    }
    UPLOADS.insert(0, item)
    return handler.reply(202, {"upload_id": item["upload_id"]})


# Onboarding and admin, as in `apps/api` (`onboarding.py`, `admin.py`).
CONSENT_VERSION = "2"
AUTH_CODE = re.compile(r"(?<![A-Z0-9-])[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{4}(?![A-Z0-9-])")
SHARE_CODE = re.compile(r"CSGO(?:-[A-Za-z0-9]{5}){5}(?![A-Za-z0-9-])")


def find_code(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(re.sub(r"\s+", "", text))
    return found.group(0) if found else None


def place_codes(auth_text: str, share_text: str) -> tuple[str | None, str | None]:
    """As the API does (`onboarding.place_codes`): two codes pasted the other way round are put
    back in place."""
    auth = find_code(AUTH_CODE, auth_text.upper())
    share = find_code(SHARE_CODE, share_text)
    if auth is None and share is None:
        swapped_auth = find_code(AUTH_CODE, share_text.upper())
        swapped_share = find_code(SHARE_CODE, auth_text)
        if swapped_auth and swapped_share:
            return swapped_auth, swapped_share
    return auth, share


def consent(
    analysis: bool = True, corpus: bool = False, version: str = CONSENT_VERSION
) -> dict[str, Any]:
    return {
        "text_version": version,
        "analysis": analysis,
        "research_corpus": analysis and corpus,
        "recorded_at": iso(NOW - dt.timedelta(days=6)),
    }


def source(enabled: bool = True, error: str | None = None) -> dict[str, Any]:
    last = iso(NOW - dt.timedelta(minutes=40))
    return {"enabled": enabled, "last_success_at": last, "last_error": error}


STATES: dict[str, dict[str, Any]] = {
    "joined": {"consent": None, "source": None},
    "consented": {"consent": consent(), "source": None},
    "followed": {"consent": consent(corpus=True), "source": source()},
    "error": {"consent": consent(), "source": source(error="403")},
    "withdrawn": {"consent": consent(analysis=False), "source": source(enabled=False)},
    "outdated": {"consent": consent(version="0"), "source": source()},
    "nokey": {"consent": consent(), "source": None, "can_add_source": False},
    "player": {"consent": consent(corpus=True), "source": source(), "admin": False},
}
ME_STATE: dict[str, Any] = {}


def set_state(name: str) -> bool:
    if name not in STATES:
        return False
    ME_STATE.clear()
    ME_STATE.update({"admin": True, "can_add_source": True} | STATES[name])
    return True


set_state("followed")


def me() -> dict[str, Any]:
    return {
        "id": mock_id(9, 1),
        "steam_id": ME,
        "display_name": "you",
        "consent_version": CONSENT_VERSION,
        **ME_STATE,
    }


def player(
    n: int,
    name: str,
    state: str,
    *,
    error: str | None = None,
    matches: int = 0,
    corpus: bool = False,
) -> dict[str, Any]:
    joined = state != "invited"
    consented = state in ("consented", "followed", "paused", "withdrawn")
    sourced = state in ("followed", "paused", "withdrawn")
    return {
        "steam_id": str(76561190000000100 + n),
        "display_name": name,
        "state": state,
        "invited_at": iso(NOW - dt.timedelta(days=12 - n)),
        "joined_at": iso(NOW - dt.timedelta(days=10 - n)) if joined else None,
        "last_seen_at": iso(NOW - dt.timedelta(hours=3 * n + 1)) if joined else None,
        "consent": consent(analysis=state != "withdrawn", corpus=corpus) if consented else None,
        "source": {
            "id": mock_id(8, n),
            "enabled": state == "followed",
            "last_success_at": iso(NOW - dt.timedelta(hours=n)) if state != "withdrawn" else None,
            "last_error": error,
        }
        if sourced
        else None,
        "matches": matches,
        "last_match_at": iso(NOW - dt.timedelta(days=n % 4)) if matches else None,
    }


# Steam accounts that signed in without an invitation and asked for one.
INVITATION_REQUESTS: list[dict[str, Any]] = [
    {
        "steam_id": "76561199000000201",
        "persona_name": "night_owl",
        "requested_at": iso(NOW - dt.timedelta(days=2)),
    },
    {
        "steam_id": "76561199000000202",
        "persona_name": None,
        "requested_at": iso(NOW - dt.timedelta(hours=5)),
    },
]


PLAYERS: list[dict[str, Any]] = [
    # The admin is a player too: erasing them from the admin answers 409 (settings only).
    player(0, "you", "followed", matches=12) | {"steam_id": ME},
    player(1, "Kestrel", "followed", matches=41, corpus=True),
    player(2, "Brindle", "followed", error="403", matches=17),
    player(3, "Oxide", "followed", error="412", matches=9),
    player(4, "Tamsin", "paused", matches=23),
    player(5, "Vireo", "consented"),
    player(6, "Quill", "joined"),
    player(7, "Marlow", "withdrawn", matches=5),
    player(8, "Juno", "invited"),
]

HEALTH: dict[str, Any] = {
    "database_bytes": 412_000_000,
    "jobs": {"done": 1284, "queued": 3, "running": 1, "failed": 2},
    "failed_jobs": [
        {
            "kind": "download",
            "attempts": 3,
            "error": "demo URL expired (HTTP 404)",
            "at": iso(NOW - dt.timedelta(hours=5)),
        },
        {
            "kind": "parse",
            "attempts": 1,
            "error": "truncated demo: unexpected end of file",
            "at": iso(NOW - dt.timedelta(days=2)),
        },
    ],
    "matches_7_days": {"ready": 58, "parsing": 1, "unavailable": 3, "failed": 1},
    "sources": {"total": 5, "paused": 1, "erroring": 2},
    "backups": {
        "last": {
            "name": "untraded-2026-10-20.dump",
            "at": iso(NOW - dt.timedelta(hours=19)),
            "bytes": 96_000_000,
        },
        "daily": 7,
        "weekly": 4,
        "offsite": {"ok": True, "at": iso(NOW - dt.timedelta(hours=18)), "target": "storage box"},
    },
    "disk": {"total": 48_000_000_000, "free": 21_500_000_000},
}


def find_source(source_id: str) -> dict[str, Any] | None:
    return next((p for p in PLAYERS if p["source"] and p["source"]["id"] == source_id), None)


def read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    size = int(handler.headers.get("content-length") or 0)
    data: dict[str, Any] = json.loads(handler.rfile.read(size) or b"{}")
    return data


class Handler(BaseHTTPRequestHandler):
    def signed_in(self) -> bool:
        return f"{COOKIE}=" in (self.headers.get("cookie") or "")

    def demo(self) -> bool:
        """The public demo's session (`/auth/demo`): read-only, as in `apps/api` (#138)."""
        return f"{COOKIE}=demo" in (self.headers.get("cookie") or "")

    def send_raw(self, gzipped: bytes) -> None:
        """A replay, as the API sends it: gzipped JSON that never changes."""
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-encoding", "gzip")
        self.send_header("cache-control", "private, max-age=86400")
        self.send_header("content-length", str(len(gzipped)))
        self.end_headers()
        self.wfile.write(gzipped)

    def reply(self, status: int, body: Any = None, headers: dict[str, str] | None = None) -> None:
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        if body is not None:
            self.send_header("content-type", "application/json")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        if path == "/health":
            return self.reply(200, {"status": "ok"})
        if path == "/auth/demo":
            cookie = f"{COOKIE}=demo; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400"
            return self.reply(303, headers={"location": f"{WEB}/", "set-cookie": cookie})
        if path == "/auth/steam":
            cookie = f"{COOKIE}=mock; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
            return self.reply(303, headers={"location": f"{WEB}/", "set-cookie": cookie})
        if not self.signed_in():
            return self.reply(401, {"detail": "not signed in"})
        if found := re.fullmatch(r"/mock/state/(\w+)", path):
            if not set_state(found[1]):
                return self.reply(404, {"detail": f"states: {', '.join(STATES)}"})
            return self.reply(303, headers={"location": f"{WEB}/"})
        if path == "/me":
            if self.demo():
                demo = me() | STATES["followed"] | {"admin": False, "can_add_source": False}
                return self.reply(200, demo | {"display_name": "demo", "demo": True})
            return self.reply(200, me() | {"demo": False})
        if found := re.fullmatch(r"/uploads/faceit/(1-[0-9a-f-]{36})", path):
            # The match's start, as FACEIT's Data API gives it (#139): two hours ago here.
            played = dt.datetime.now(dt.UTC).replace(microsecond=0) - dt.timedelta(hours=2)
            return self.reply(200, {"played_at": played.isoformat().replace("+00:00", "Z")})
        if found := re.fullmatch(r"/mock/uploads/(\w+)", path):
            choice = None if found[1] == "none" else found[1]
            if choice is not None and choice not in UPLOAD_STATUS:
                return self.reply(404, {"detail": f"refusals: none, {', '.join(UPLOAD_STATUS)}"})
            UPLOAD_STATE["refusal"] = choice
            return self.reply(303, headers={"location": f"{WEB}/upload"})
        if path == "/uploads":
            return self.reply(
                200,
                {
                    "items": [upload_line(u) for u in UPLOADS],
                    "refusal": UPLOAD_STATE["refusal"],
                    "max_bytes": UPLOAD_MAX,
                },
            )
        if path.startswith("/admin/") and not ME_STATE["admin"]:
            return self.reply(403, {"detail": "admins only"})
        if path == "/admin/players":
            return self.reply(200, {"items": PLAYERS})
        if path == "/admin/health":
            return self.reply(200, HEALTH)
        if path == "/admin/invitation-requests":
            return self.reply(200, {"items": INVITATION_REQUESTS})
        offset = int((re.search(r"offset=(\d+)", query) or [0, 0])[1])
        if path == "/matches":
            return self.reply(
                200, {"items": MATCHES[offset : offset + 30], "limit": 30, "offset": offset}
            )
        if path == "/sessions":
            items = [summary(s) for s in SESSIONS[offset : offset + 20]]
            return self.reply(200, {"items": items, "limit": 20, "offset": offset})
        if found := re.fullmatch(r"/sessions/([0-9a-f-]+)", path):
            for n, session in enumerate(SESSIONS):
                if session["id"] == found[1]:
                    return self.reply(200, report(n))
        if found := re.fullmatch(r"/matches/([0-9a-f-]+)/rounds/(\d+)/replay", path):
            n = int(found[2])
            for match in MATCHES:
                if match["id"] == found[1] and match["status"] == "ready":
                    data = replay_gz(match, n) if 1 <= n <= match["rounds_played"] else None
                    if data is not None:
                        return self.send_raw(data)
            return self.reply(404, {"detail": "no such replay"})
        if found := re.fullmatch(r"/matches/([0-9a-f-]+)/players/(\d+)/rating", path):
            rating = player_rating(found[1], found[2])
            return self.reply(200 if rating else 404, rating or {"detail": "no such player"})
        if found := re.fullmatch(r"/matches/([0-9a-f-]+)/players/(\d+)", path):
            return self.reply(200, player_metrics(found[1], found[2]))
        if found := re.fullmatch(r"/matches/([0-9a-f-]+)", path):
            if found[1] == BROKEN_MATCH:
                return self.reply(500, {"detail": "internal error"})
            for match in MATCHES:
                if match["id"] == found[1]:
                    return self.reply(200, match_detail(match))
        return self.reply(404, {"detail": "not found"})

    def do_POST(self) -> None:
        if self.demo() and not self.path.startswith("/auth/logout"):
            return self.reply(403, {"detail": "demo"})
        path, _, query = self.path.partition("?")
        if path == "/uploads":
            if not self.signed_in():
                return self.reply(401, {"detail": "not signed in"})
            return receive_upload(self, query)
        if path == "/auth/invitation-request":
            # The real API checks the signed cookie of a refused sign-in; here, it is recorded.
            return self.reply(303, headers={"location": f"{WEB}/?signin=requested"})
        size = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(size) or b"{}")
        if self.path == "/auth/logout":
            return self.reply(204, headers={"set-cookie": f"{COOKIE}=; Path=/; Max-Age=0"})
        if not self.signed_in():
            return self.reply(401, {"detail": "not signed in"})
        if self.path == "/me/erase":
            if body.get("confirm") is not True:
                return self.reply(422, {"detail": {"field": "confirm"}})
            # Signed out at once; signing in again starts from a followed player.
            set_state("followed")
            return self.reply(202, headers={"set-cookie": f"{COOKIE}=; Path=/; Max-Age=0"})
        if self.path == "/me/consent":
            if body.get("analysis") and body.get("text_version") != CONSENT_VERSION:
                return self.reply(409, {"detail": "this is not the current consent text"})
            ME_STATE["consent"] = consent(
                analysis=bool(body.get("analysis")),
                corpus=bool(body.get("research_corpus")),
                version=body.get("text_version") or CONSENT_VERSION,
            )
            if not body.get("analysis") and ME_STATE["source"]:
                ME_STATE["source"]["enabled"] = False
            return self.reply(204)
        if self.path.startswith("/admin/") and not ME_STATE["admin"]:
            return self.reply(403, {"detail": "admins only"})
        if self.path == "/admin/invitations":
            steam_id = str(body.get("steam_id", "")).strip()
            name = str(body.get("display_name", "")).strip()
            if not re.fullmatch(r"7656119\d{10}", steam_id):
                return self.reply(422, {"detail": {"field": "steam_id"}})
            if not name or len(name) > 64:
                return self.reply(422, {"detail": {"field": "display_name"}})
            if steam_id == ME or any(p["steam_id"] == steam_id for p in PLAYERS):
                return self.reply(409, {"detail": "already invited or a user"})
            invited = player(0, name, "invited") | {"steam_id": steam_id, "invited_at": iso(NOW)}
            PLAYERS.insert(0, invited)
            INVITATION_REQUESTS[:] = [r for r in INVITATION_REQUESTS if r["steam_id"] != steam_id]
            return self.reply(201, invited)
        if found := re.fullmatch(r"/admin/sources/([0-9a-f-]+)/(pause|resume)", self.path):
            owner = find_source(found[1])
            if owner is None:
                return self.reply(404, {"detail": "no such source"})
            owner["source"]["enabled"] = found[2] == "resume"
            if owner["state"] in ("followed", "paused"):
                owner["state"] = "followed" if found[2] == "resume" else "paused"
            return self.reply(204)
        if found := re.fullmatch(r"/advice/([0-9a-f-]+)/feedback", self.path):
            vote = body.get("vote")
            if vote not in (-1, 0, 1):
                return self.reply(422, {"detail": "vote must be -1, 0 or 1"})
            if vote:
                VOTES[found[1]] = vote
            else:
                VOTES.pop(found[1], None)
            return self.reply(204)
        return self.reply(404, {"detail": "not found"})

    def do_PUT(self) -> None:
        if self.demo() and not self.path.startswith("/auth/logout"):
            return self.reply(403, {"detail": "demo"})
        body = read_body(self)
        if not self.signed_in():
            return self.reply(401, {"detail": "not signed in"})
        if self.path != "/me/source":
            return self.reply(404, {"detail": "not found"})
        if not ME_STATE["can_add_source"]:
            return self.reply(503, {"detail": "codes cannot be stored here"})
        if not (ME_STATE["consent"] and ME_STATE["consent"]["analysis"]):
            return self.reply(409, {"detail": "consent first"})
        auth_code, share_code = place_codes(
            str(body.get("auth_code", "")), str(body.get("share_code", ""))
        )
        if auth_code is None:
            return self.reply(422, {"detail": {"field": "auth_code"}})
        if share_code is None:
            return self.reply(422, {"detail": {"field": "share_code"}})
        if auth_code == "STEA-MDOWN-0503":
            return self.reply(503, {"detail": "Steam did not answer"})
        if auth_code == "XXXX-XXXXX-XXXX":
            return self.reply(422, {"detail": {"field": "auth_code"}})
        if share_code == "CSGO-00000-00000-00000-00000-00000":
            return self.reply(422, {"detail": {"field": "share_code"}})
        ME_STATE["source"] = source()
        return self.reply(204)

    def do_DELETE(self) -> None:
        if self.demo() and not self.path.startswith("/auth/logout"):
            return self.reply(403, {"detail": "demo"})
        if not self.signed_in():
            return self.reply(401, {"detail": "not signed in"})
        if not ME_STATE["admin"]:
            return self.reply(403, {"detail": "admins only"})
        if found := re.fullmatch(r"/admin/players/(\d+)", self.path):
            if found[1] == ME:
                return self.reply(409, {"detail": "erase your own account from your settings"})
            for p in PLAYERS:
                if p["steam_id"] == found[1]:
                    PLAYERS.remove(p)
                    return self.reply(202)
            return self.reply(404, {"detail": "no such player"})
        if found := re.fullmatch(r"/admin/invitation-requests/(\d+)", self.path):
            for r in INVITATION_REQUESTS:
                if r["steam_id"] == found[1]:
                    INVITATION_REQUESTS.remove(r)
                    return self.reply(204)
            return self.reply(404, {"detail": "no such request"})
        if found := re.fullmatch(r"/admin/invitations/(\d+)", self.path):
            for p in PLAYERS:
                if p["steam_id"] == found[1] and p["state"] == "invited":
                    PLAYERS.remove(p)
                    return self.reply(204)
            return self.reply(404, {"detail": "no such invitation"})
        if found := re.fullmatch(r"/admin/sources/([0-9a-f-]+)", self.path):
            owner = find_source(found[1])
            if owner is None:
                return self.reply(404, {"detail": "no such source"})
            owner["source"] = None
            if owner["state"] in ("followed", "paused"):
                owner["state"] = "consented"
            return self.reply(204)
        return self.reply(404, {"detail": "not found"})

    def log_message(self, *_: object) -> None:
        pass


if __name__ == "__main__":
    print(f"mock Untraded API on http://127.0.0.1:{PORT} (web: {WEB})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
