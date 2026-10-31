// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { EXECS, LINEUPS, MATRIX, MEMBERS, STATS, STRATS } from "../src/lib/team-preview/data";
import { canEdit, canSee, EMPTY, ownAccess, readSaved } from "../src/lib/team-preview/rules";
import { allows, may, PAGES, ROLES, text } from "../src/lib/team-preview/types";

describe("team preview", () => {
  it("orders the levels: manage allows edit, edit allows view", () => {
    expect(allows("manage", "edit")).toBe(true);
    expect(allows("edit", "view")).toBe(true);
    expect(allows("view", "edit")).toBe(false);
    expect(allows("none", "view")).toBe(false);
  });

  it("lets the owner see and edit everything, others as the item says", () => {
    const access = { view: ["coach" as const], edit: [] };
    expect(may(access, "owner", "edit")).toBe(true);
    expect(may(access, "coach", "view")).toBe(true);
    expect(may(access, "coach", "edit")).toBe(false);
    expect(may(access, "player", "view")).toBe(false);
  });

  it("writes invented texts in the visitor's language, typed ones as typed", () => {
    expect(text({ fr: "Défaut", en: "Default" }, "fr")).toBe("Défaut");
    expect(text({ fr: "Défaut", en: "Default" }, "en")).toBe("Default");
    expect(text("as typed", "fr")).toBe("as typed");
  });

  it("keeps the invented team consistent", () => {
    for (const page of PAGES) for (const role of ROLES) expect(MATRIX[page][role]).toBeDefined();
    expect(MATRIX.roster.owner).toBe("manage");
    const ids = new Set(MEMBERS.map((m) => m.id));
    const lineups = new Set(LINEUPS.map((l) => l.id));
    for (const exec of EXECS) {
      for (const task of exec.tasks) {
        expect(ids.has(task.member)).toBe(true);
        if (task.lineup) expect(lineups.has(task.lineup)).toBe(true);
      }
    }
    for (const strat of STRATS)
      for (const step of strat.steps) expect(ids.has(step.member)).toBe(true);
    for (const lineup of LINEUPS) expect(ids.has(lineup.author)).toBe(true);
  });

  it("needs both the page level and the item's access to see or edit", () => {
    const access = { view: ["player" as const], edit: ["player" as const] };
    expect(canEdit("edit", access, "player")).toBe(true);
    // A role that only views the page never edits, whatever the item says.
    expect(canEdit("view", access, "player")).toBe(false);
    expect(canEdit("edit", { view: ["player"], edit: [] }, "player")).toBe(false);
    expect(canSee("view", access, "player")).toBe(true);
    expect(canSee("none", access, "player")).toBe(false);
    expect(canSee("view", access, "viewer")).toBe(false);
    expect(canEdit("view", access, "owner")).toBe(false);
    expect(canEdit("manage", { view: [], edit: [] }, "owner")).toBe(true);
  });

  it("keeps what one adds visible and editable to one's own role", () => {
    expect(ownAccess({ view: [], edit: ["coach"] }, "player")).toEqual({
      view: ["player"],
      edit: ["coach", "player"],
    });
    expect(ownAccess({ view: [], edit: [] }, "owner")).toEqual({ view: [], edit: [] });
  });

  it("reads back broken or old browser data without breaking", () => {
    expect(readSaved(null)).toEqual(EMPTY);
    expect(readSaved("not json")).toEqual(EMPTY);
    expect(readSaved(JSON.stringify({ version: 0 }))).toEqual(EMPTY);
    const read = readSaved(
      JSON.stringify({
        version: 1,
        viewAs: "admin",
        matrix: { lineups: { coach: "view", player: "everything" }, strats: null },
        lineups: "nope",
        execs: [{ id: "e1", access: { view: ["player", "hacker"], edit: [] } }, { id: 3 }, null],
        access: { "l-mirage-ct": { view: ["coach"], edit: [] }, bad: { view: "x" } },
      }),
    );
    expect(read.viewAs).toBe("owner");
    expect(read.matrix.lineups.coach).toBe("view");
    expect(read.matrix.lineups.player).toBe(MATRIX.lineups.player);
    expect(read.matrix.strats).toEqual(MATRIX.strats);
    expect(read.matrix.roster.owner).toBe("manage");
    expect(read.lineups).toEqual([]);
    expect(read.execs.map((e) => [e.id, e.access.view])).toEqual([["e1", ["player"]]]);
    expect(Object.keys(read.access)).toEqual(["l-mirage-ct"]);
  });

  it("keeps the invented stats consistent", () => {
    const lists = [STATS.sites, STATS.postplant, STATS.retakes];
    for (const list of lists)
      for (const row of list)
        expect(row.won).toBeLessThanOrEqual("tried" in row ? row.tried : row.rounds);
    for (const row of STATS.execs) {
      expect(row.won).toBeLessThanOrEqual(row.run);
      expect(EXECS.some((e) => e.id === row.exec)).toBe(true);
    }
    for (const row of [...STATS.setups, ...STATS.economy])
      expect(row.won).toBeLessThanOrEqual(row.rounds);
    expect(STATS.economy.reduce((sum, row) => sum + row.rounds, 0)).toBe(STATS.rounds);
  });
});
