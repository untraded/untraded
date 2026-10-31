// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { EXECS, LINEUPS, MATRIX, MEMBERS, STRATS } from "../src/lib/team-preview/data";
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
});
