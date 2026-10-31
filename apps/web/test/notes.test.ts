// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { demoNote } from "../src/lib/notes";

describe("demoNote", () => {
  it("reads the parser's counted adjustments", () => {
    expect(demoNote("kill: 1 disconnections dropped (not deaths)")).toEqual({
      kind: "disconnections",
      count: 1,
    });
    expect(demoNote("kill: 4 kills of bots (no death counted)")).toEqual({
      kind: "bots",
      count: 4,
    });
  });

  it("reads what the demo lacks", () => {
    expect(demoNote("bomb: no bomb event")).toEqual({ kind: "bomb" });
    expect(demoNote("kill: no player_death event")).toEqual({ kind: "kills" });
    expect(demoNote("grenade: no projectile in the demo")).toEqual({ kind: "grenades" });
    expect(demoNote("shot: no weapon_fire event")).toEqual({ kind: "shots" });
  });

  it("keeps a note it does not know as written", () => {
    expect(demoNote("tick: something new")).toEqual({ kind: "other", text: "tick: something new" });
  });
});
