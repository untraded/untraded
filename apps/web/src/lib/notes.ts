// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The parser's notes on a demo (`match.unavailable`, written in `untraded.parsing` for
// developers), read for players: what is missing from the demo, or how the analysis adjusted it.

/** A note, by its kind: a table the demo lacks, an adjustment with its count, or a note the web
 * does not know yet (shown as written). */
export type DemoNote =
  | { kind: "bomb" | "damage" | "blind" | "kills" | "grenades" | "shots" }
  | { kind: "disconnections" | "bots"; count: number }
  /** A side surrendered in the freeze time after round `after`: one more round, not played,
   * counts for `winner` in the official score. */
  | { kind: "surrender"; after: number; winner: "CT" | "T" }
  | { kind: "other"; text: string };

const MISSING: [RegExp, DemoNote["kind"]][] = [
  [/^bomb: /, "bomb"],
  [/^damage: /, "damage"],
  [/^blind: /, "blind"],
  [/^kill: no player_death/, "kills"],
  [/^grenade: /, "grenades"],
  [/^shot: /, "shots"],
];

export function demoNote(note: string): DemoNote {
  const surrender =
    /^round: the (?:CT|T) side surrendered during the freeze time after round (\d+);.* for the (CT|T) side/.exec(
      note,
    );
  if (surrender) {
    return { kind: "surrender", after: Number(surrender[1]), winner: surrender[2] as "CT" | "T" };
  }
  const counted = /^kill: (\d+) (disconnections dropped|kills of bots)/.exec(note);
  if (counted) {
    const kind = counted[2] === "kills of bots" ? "bots" : "disconnections";
    return { kind, count: Number(counted[1]) };
  }
  for (const [pattern, kind] of MISSING) {
    if (pattern.test(note)) return { kind } as DemoNote;
  }
  return { kind: "other", text: note };
}
