// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import {
  diskState,
  dumpState,
  jobsState,
  offsiteState,
  overall,
  sourcesState,
} from "../src/lib/admin-health";
import type { Health } from "../src/lib/api";

const NOW = Date.parse("2026-11-10T12:00:00Z");
const hoursAgo = (h: number) => new Date(NOW - h * 3_600_000).toISOString();
const backups = (last: Health["backups"]["last"]): Health["backups"] => ({
  last,
  daily: 7,
  weekly: 4,
  offsite: null,
});

describe("dumpState", () => {
  it("fails without a dump, is late past 30 hours, else ok", () => {
    expect(dumpState(backups(null), NOW)).toBe("fail");
    expect(dumpState(backups({ name: "a.dump", at: hoursAgo(31), bytes: 1 }), NOW)).toBe("warn");
    expect(dumpState(backups({ name: "a.dump", at: hoursAgo(9), bytes: 1 }), NOW)).toBe("ok");
    expect(dumpState(backups({ name: "a.dump", at: "soon", bytes: 1 }), NOW)).toBe("unknown");
  });
});

describe("offsiteState", () => {
  it("reads what the copy wrote", () => {
    expect(offsiteState(null, NOW).state).toBe("warn");
    const ok = offsiteState({ ok: true, at: hoursAgo(8), message: "copied" }, NOW);
    expect(ok).toEqual({ state: "ok", at: hoursAgo(8), message: "copied", late: false });
    expect(offsiteState({ ok: true, at: hoursAgo(40) }, NOW)).toMatchObject({
      state: "warn",
      late: true,
    });
    expect(offsiteState({ ok: false, at: hoursAgo(2), message: "copy failed" }, NOW)).toMatchObject(
      { state: "fail", message: "copy failed" },
    );
    expect(offsiteState({ error: "offsite.json is not JSON" }, NOW)).toMatchObject({
      state: "fail",
      message: "offsite.json is not JSON",
      at: null,
    });
  });

  it("drops a date that does not parse", () => {
    expect(offsiteState({ ok: true, at: "garbage" }, NOW)).toMatchObject({
      state: "unknown",
      at: null,
    });
    expect(offsiteState({ ok: false, at: "" }, NOW)).toMatchObject({ state: "fail", at: null });
  });

  it("does not trust a shape it does not know", () => {
    expect(offsiteState({ ok: "yes", at: hoursAgo(1) }, NOW).state).toBe("unknown");
    expect(offsiteState({ ok: true }, NOW).state).toBe("unknown");
    expect(offsiteState({ ok: true, at: 12, message: { a: 1 } }, NOW)).toMatchObject({
      state: "unknown",
      at: null,
      message: null,
    });
  });
});

describe("diskState", () => {
  it("grades the used share", () => {
    expect(diskState(null)).toEqual({ state: "unknown", used: null });
    expect(diskState({ total: 0, free: 0 }).state).toBe("unknown");
    expect(diskState({ total: 100, free: 50 })).toEqual({ state: "ok", used: 0.5 });
    expect(diskState({ total: 100, free: 20 }).state).toBe("warn");
    expect(diskState({ total: 100, free: 10 }).state).toBe("fail");
  });
});

describe("jobs, sources and the summary", () => {
  it("flags failures and errors, and sums up by the worst", () => {
    const health = { failed_jobs: [] } as unknown as Health;
    expect(jobsState(health)).toBe("ok");
    expect(
      jobsState({ failed_jobs: [{ kind: "parse", attempts: 1, error: null, at: "" }] } as Health),
    ).toBe("warn");
    expect(sourcesState({ total: 3, paused: 0, erroring: 1 })).toBe("warn");
    expect(sourcesState({ total: 3, paused: 1, erroring: 0 })).toBe("ok");
    expect(overall(["ok", "warn", "fail", "warn"])).toEqual({ state: "fail", count: 1 });
    expect(overall(["ok", "warn", "unknown", "warn"])).toEqual({ state: "warn", count: 2 });
    expect(overall(["ok", "ok"])).toEqual({ state: "ok", count: 2 });
    expect(overall(["ok", "unknown", "ok"])).toEqual({ state: "unknown", count: 1 });
  });
});
