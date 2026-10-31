// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Round replays for the 2D viewer (`docs/replay-format.md`, version 2), and what the viewer
// computes from them: where a moment falls between samples, where a world point falls on the
// radar, the level, the clock and the bomb. Pure, tested without a browser.

export type Side = "CT" | "T";

/** Where world points fall on the map's 1024-pixel radar. */
export interface RadarTransform {
  pos_x: number;
  pos_y: number;
  scale: number;
  /** World `z` under which a point is on the lower level; null for a map with one level. */
  lower_below: number | null;
}

export interface ReplayPlayer {
  steamid: string;
  name: string;
  team: "A" | "B";
  side: Side;
  x: (number | null)[];
  y: (number | null)[];
  z: (number | null)[];
  yaw: (number | null)[];
  hp: (number | null)[];
  armor: (number | null)[];
  alive: (number | null)[];
  flash: (number | null)[];
  scoped: (number | null)[];
  defusing: (number | null)[];
  weapon: (number | null)[];
}

export interface ReplayKill {
  tick: number;
  attacker: string | null;
  victim: string;
  assister: string | null;
  weapon: string;
  headshot: boolean;
  wallbang: boolean;
  through_smoke: boolean;
  team_kill: boolean;
  attacker_x: number | null;
  attacker_y: number | null;
  attacker_z: number | null;
  victim_x: number;
  victim_y: number;
  victim_z: number;
}

export type GrenadeType = "flash" | "he" | "smoke" | "molotov" | "incendiary" | "decoy";

export interface ReplayGrenade {
  id: number;
  type: GrenadeType;
  thrower: string | null;
  side: Side | null;
  throw_tick: number;
  detonate_tick: number | null;
  /** When a smoke clears or a fire dies out. */
  end_tick: number | null;
  detonate: [number, number, number] | null;
  path: { ticks: number[]; x: number[]; y: number[]; z: number[] };
}

export type BombEventType =
  | "plant_begin"
  | "planted"
  | "defuse_begin"
  | "defused"
  | "exploded"
  | "dropped"
  | "picked_up";

/** One credit of a kill, a plant or a defuse: how much it moved the player's side's chance of
 * winning the round, from -1 to 1. */
export interface ReplaySwing {
  tick: number;
  event: "kill" | "plant" | "defuse";
  player: string;
  side: Side;
  swing: number;
}

/** The counter-terrorists' chance of winning the round over time (`docs/winprob.md`): the curve
 * steps at each event (two points on its tick, before and after) and ends on the result. */
export interface ReplayWinProb {
  model: string;
  ticks: number[];
  p_ct: number[];
  swings: ReplaySwing[];
}

export interface Replay {
  version: number;
  match_id: string;
  round: number;
  map: string;
  tickrate: number;
  radar: RadarTransform | null;
  start_tick: number;
  freeze_end_tick: number;
  end_tick: number;
  winner_side: Side | null;
  reason: string | null;
  ticks: number[];
  weapons: string[];
  players: ReplayPlayer[];
  kills: ReplayKill[];
  grenades: ReplayGrenade[];
  blinds: { tick: number; victim: string; flasher: string | null; duration: number }[];
  bomb: {
    events: { tick: number; type: BombEventType; player: string | null; site: string | null }[];
    planted_at: [number, number, number] | null;
  };
  /** Null for a round the model does not cover (no winner, or an end such as a surrender). */
  winprob: ReplayWinProb | null;
}

/** The format version this viewer reads. */
export const REPLAY_VERSION = 2;
/** Premier: a round lasts 1:55 after the freeze time, the bomb 40 s once planted. */
export const ROUND_SECONDS = 115;
export const BOMB_SECONDS = 40;
/** Radius of a smoke and of a fire, in world units (close enough to draw them). */
export const SMOKE_RADIUS = 144;
export const FIRE_RADIUS = 120;
/** Maps whose radar has a lower level (`/radars/{map}_lower.svg`). */
export const TWO_LEVELS = new Set(["de_nuke", "de_train", "de_vertigo"]);
/** Maps with one of our radars (`/radars/{map}.svg`). */
export const RADAR_MAPS = new Set([
  "de_ancient",
  "de_anubis",
  "de_cache",
  "de_dust2",
  "de_inferno",
  "de_mirage",
  "de_nuke",
  "de_overpass",
  "de_train",
  "de_vertigo",
]);

/** Two samples around a tick and how far between them: `i0 = i1` at the ends. */
export interface Sample {
  i0: number;
  i1: number;
  f: number;
}

export function sampleAt(ticks: number[], tick: number): Sample {
  const last = ticks.length - 1;
  if (last < 0 || tick <= (ticks[0] ?? 0)) return { i0: 0, i1: 0, f: 0 };
  if (tick >= (ticks[last] ?? 0)) return { i0: last, i1: last, f: 0 };
  let lo = 0;
  let hi = last;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if ((ticks[mid] ?? 0) <= tick) lo = mid;
    else hi = mid;
  }
  const a = ticks[lo] ?? 0;
  const b = ticks[hi] ?? a;
  return { i0: lo, i1: hi, f: b === a ? 0 : (tick - a) / (b - a) };
}

/** A value between two samples; the known one when the other is missing. */
export function between(values: (number | null)[], { i0, i1, f }: Sample): number | null {
  const a = values[i0] ?? null;
  const b = values[i1] ?? null;
  if (a === null) return b;
  if (b === null) return a;
  return a + (b - a) * f;
}

/** An angle between two samples, the short way round (359° to 1° goes through 0°). */
export function angleBetween(values: (number | null)[], { i0, i1, f }: Sample): number | null {
  const a = values[i0] ?? null;
  const b = values[i1] ?? null;
  if (a === null) return b;
  if (b === null) return a;
  const turn = ((((b - a) % 360) + 540) % 360) - 180;
  return a + turn * f;
}

/** The state at the nearer sample: for what does not blend (alive, weapon). */
export function nearest<T>(values: (T | null)[], { i0, i1, f }: Sample): T | null {
  return (f < 0.5 ? values[i0] : values[i1]) ?? null;
}

/**
 * World to the 1024-pixel frame the radars are drawn in: the map's transform, or, when the map has
 * none (`radar: null`), a square fit on everything that moves in the round.
 */
export interface Frame {
  toPixel: (x: number, y: number) => [number, number];
  /** Pixels per world unit. */
  scale: number;
  /** Whether the frame is the map's: then a radar can be drawn under it. */
  radar: boolean;
}

export function frameOf(replay: Pick<Replay, "radar" | "players">): Frame {
  const r = replay.radar;
  if (r) {
    return {
      toPixel: (x, y) => [(x - r.pos_x) / r.scale, (r.pos_y - y) / r.scale],
      scale: 1 / r.scale,
      radar: true,
    };
  }
  let x0 = Number.POSITIVE_INFINITY;
  let x1 = Number.NEGATIVE_INFINITY;
  let y0 = Number.POSITIVE_INFINITY;
  let y1 = Number.NEGATIVE_INFINITY;
  for (const player of replay.players) {
    player.x.forEach((x, i) => {
      const y = player.y[i];
      if (x === null || y === null || y === undefined) return;
      x0 = Math.min(x0, x);
      x1 = Math.max(x1, x);
      y0 = Math.min(y0, y);
      y1 = Math.max(y1, y);
    });
  }
  if (!Number.isFinite(x0)) return { toPixel: () => [512, 512], scale: 1, radar: false };
  // A margin of 6 % around the round's extent, centred in the square.
  const span = Math.max(x1 - x0, y1 - y0, 1) * 1.12;
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  const scale = 1024 / span;
  return {
    toPixel: (x, y) => [512 + (x - cx) * scale, 512 - (y - cy) * scale],
    scale,
    radar: false,
  };
}

export type Level = "upper" | "lower";

/** Whether the round is drawn on two levels: a map with a lower level, and its transform. */
export function hasLevels(replay: Pick<Replay, "radar">): boolean {
  return replay.radar?.lower_below !== null && replay.radar?.lower_below !== undefined;
}

export function levelOf(replay: Pick<Replay, "radar">, z: number | null): Level {
  const below = replay.radar?.lower_below;
  return below !== null && below !== undefined && z !== null && z < below ? "lower" : "upper";
}

/**
 * The level a player stands on at a tick, for the viewer to show it on its own. Where their height
 * is not known at that moment (no sample yet, dead), their last known height counts, else the
 * next one; upper when there is none, or when the map has one level.
 */
export function levelAt(
  replay: Pick<Replay, "radar" | "ticks" | "players">,
  steamid: string | null,
  tick: number,
): Level {
  const player = replay.players.find((p) => p.steamid === steamid);
  if (!player || !hasLevels(replay)) return "upper";
  const sample = sampleAt(replay.ticks, tick);
  let z = between(player.z, sample);
  for (let i = sample.i0; z === null && i >= 0; i--) z = player.z[i] ?? null;
  for (let i = sample.i1; z === null && i < player.z.length; i++) z = player.z[i] ?? null;
  return levelOf(replay, z);
}

/** What the clock shows: the buy time left, the round time left, or the bomb's. */
export function clock(
  replay: Pick<Replay, "tickrate" | "freeze_end_tick" | "bomb">,
  tick: number,
): { kind: "freeze" | "round" | "bomb"; seconds: number } {
  const planted = replay.bomb.events.find((e) => e.type === "planted");
  if (planted && tick >= planted.tick) {
    return { kind: "bomb", seconds: BOMB_SECONDS - (tick - planted.tick) / replay.tickrate };
  }
  if (tick < replay.freeze_end_tick) {
    return { kind: "freeze", seconds: (replay.freeze_end_tick - tick) / replay.tickrate };
  }
  return {
    kind: "round",
    seconds: ROUND_SECONDS - (tick - replay.freeze_end_tick) / replay.tickrate,
  };
}

/** Seconds as the game's clock writes them: `1:05`, never below `0:00`. */
export function clockText(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** Who carries the bomb at a tick: `null` once dropped or planted, or when unknown. */
export function bombCarrier(replay: Pick<Replay, "bomb">, tick: number): string | null {
  let carrier: string | null = null;
  for (const event of replay.bomb.events) {
    if (event.tick > tick) break;
    if (event.type === "picked_up") carrier = event.player;
    if (event.type === "dropped" || event.type === "planted") carrier = null;
  }
  return carrier;
}

/** The tick the viewer opens on: the one asked for, within the round, else the freeze end. */
export function startTick(
  replay: Pick<Replay, "start_tick" | "end_tick" | "freeze_end_tick">,
  asked: number | null,
): number {
  if (asked === null || !Number.isFinite(asked)) return replay.freeze_end_tick;
  return Math.min(replay.end_tick, Math.max(replay.start_tick, asked));
}

/**
 * The kill at a moment to review, if it is one: a report opens the viewer 5 s before its event, so
 * the kill within a second of `moment`, the highlighted player's first, else the nearest. Null
 * when the moment is not a kill (a flash on a teammate, a position).
 */
export function momentKill(
  replay: Pick<Replay, "kills" | "tickrate">,
  moment: number,
  focus: string | null,
): ReplayKill | null {
  const near = replay.kills
    .filter((kill) => Math.abs(kill.tick - moment) <= replay.tickrate)
    .sort((a, b) => Math.abs(a.tick - moment) - Math.abs(b.tick - moment));
  return near.find((kill) => kill.victim === focus || kill.attacker === focus) ?? near[0] ?? null;
}

/** A weapon as the viewer names it: every knife is a knife, the bomb is C4. */
export function weaponKind(name: string | null | undefined): "knife" | "c4" | null {
  if (!name) return null;
  if (/knife|bayonet|karambit|dagger/i.test(name)) return "knife";
  if (/^c4|c4 explosive/i.test(name)) return "c4";
  return null;
}

/** Kill weapons come with their internal names (`ak47`): the usual ones, as players say them. */
const KILL_WEAPONS: Record<string, string> = {
  ak47: "AK-47",
  m4a1: "M4A4",
  m4a1_silencer: "M4A1-S",
  awp: "AWP",
  ssg08: "SSG 08",
  deagle: "Desert Eagle",
  glock: "Glock-18",
  usp_silencer: "USP-S",
  hkp2000: "P2000",
  p250: "P250",
  fiveseven: "Five-SeveN",
  tec9: "Tec-9",
  cz75a: "CZ75-Auto",
  elite: "Dual Berettas",
  revolver: "R8 Revolver",
  galilar: "Galil AR",
  famas: "FAMAS",
  sg556: "SG 553",
  aug: "AUG",
  mac10: "MAC-10",
  mp9: "MP9",
  mp7: "MP7",
  mp5sd: "MP5-SD",
  ump45: "UMP-45",
  p90: "P90",
  bizon: "PP-Bizon",
  nova: "Nova",
  xm1014: "XM1014",
  mag7: "MAG-7",
  sawedoff: "Sawed-Off",
  m249: "M249",
  negev: "Negev",
  g3sg1: "G3SG1",
  scar20: "SCAR-20",
  hegrenade: "HE",
  inferno: "Molotov",
  taser: "Zeus x27",
};

/** A kill's weapon, readable; `null` for a knife (the viewer says "knife" in the user's language). */
export function killWeapon(name: string): string | null {
  if (weaponKind(name) === "knife") return null;
  return KILL_WEAPONS[name] ?? name;
}
