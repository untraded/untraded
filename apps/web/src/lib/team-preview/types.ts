// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The team mode preview: what a team, its people and its tactical book look like. A mock-up with
// invented data and no API: what a visitor adds stays in their browser.

export const ROLES = ["owner", "coach", "player", "viewer"] as const;
export type Role = (typeof ROLES)[number];

export const PAGES = ["roster", "lineups", "execs", "strats", "stats"] as const;
export type Page = (typeof PAGES)[number];

/** What a role may do on a page, each level including the ones before it. */
export const LEVELS = ["none", "view", "edit", "manage"] as const;
export type Level = (typeof LEVELS)[number];
export type Matrix = Record<Page, Record<Role, Level>>;

export const MAPS = ["mirage", "inferno", "ancient", "nuke", "anubis", "dust2", "train"] as const;
export type MapId = (typeof MAPS)[number];
export type Side = "T" | "CT";
export const SITES = ["A", "B", "mid"] as const;
export type Site = (typeof SITES)[number];

export const GRENADES = ["smoke", "flash", "molotov", "he"] as const;
export type Grenade = (typeof GRENADES)[number];
export const THROWS = ["stand", "jump", "run", "walk", "runjump"] as const;
export type Throw = (typeof THROWS)[number];

export const STRAT_KINDS = ["default", "pistol", "eco", "antieco", "retake"] as const;
export type StratKind = (typeof STRAT_KINDS)[number];

export const IN_GAME = ["igl", "entry", "awp", "support", "lurker", "anchor", "rotator"] as const;
export type InGame = (typeof IN_GAME)[number];

/** A text of the invented data, in both languages; what a visitor types stays as typed. */
export type Text = string | { fr: string; en: string };

/** Who sees an item and who may change it. */
export interface Access {
  view: Role[];
  edit: Role[];
}

export interface Member {
  id: string;
  name: string;
  role: Role;
  /** On the roster: a starter, a stand-in, or not a player. */
  roster: "starter" | "standin" | null;
  inGame: InGame[];
}

export interface Lineup {
  id: string;
  map: MapId;
  side: Side;
  site: Site;
  grenade: Grenade;
  title: Text;
  /** Where to stand, and what to aim at. */
  from: Text;
  aim: Text;
  throw: Throw;
  /** The console command that puts a player on the spot (`setpos x y z; setang p y 0`). */
  setpos: string;
  /** The key of a clip the visitor sent (IndexedDB), else a neutral frame. */
  clip: string | null;
  author: string;
  access: Access;
  /** Added in this browser: the visitor may remove it. */
  local?: boolean;
}

export interface ExecTask {
  member: string;
  task: Text;
  lineup?: string;
}

export interface Exec {
  id: string;
  map: MapId;
  site: Site;
  title: Text;
  /** When it starts, on the round clock. */
  timing: string;
  tasks: ExecTask[];
  steps: Text[];
  access: Access;
  local?: boolean;
}

export interface Strat {
  id: string;
  map: MapId;
  side: Side;
  kind: StratKind;
  title: Text;
  steps: { member: string; text: Text }[];
  notes: Text;
  tags: string[];
  access: Access;
  local?: boolean;
}

/** Whether a level allows another: `edit` allows `view`. */
export function allows(level: Level, wanted: Level): boolean {
  return LEVELS.indexOf(level) >= LEVELS.indexOf(wanted);
}

/** Whether a role may see, or change, an item: the owner always may. */
export function may(access: Access, role: Role, what: "view" | "edit"): boolean {
  return role === "owner" || access[what].includes(role);
}

export function text(value: Text, locale: string): string {
  return typeof value === "string" ? value : locale === "fr" ? value.fr : value.en;
}
