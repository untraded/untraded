// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import {
  fromLocalInput,
  guessPlayedAt,
  isDemoName,
  sendError,
  toLocalInput,
} from "../src/lib/upload";

describe("upload", () => {
  it("knows a demo by its name", () => {
    expect(isDemoName("1-abc-de_mirage.dem.zst")).toBe(true);
    expect(isDemoName("match730.DEM.BZ2")).toBe(true);
    expect(isDemoName("scrim.dem")).toBe(true);
    expect(isDemoName("scrim.dem.gz")).toBe(true);
    expect(isDemoName("demo.zip")).toBe(false);
    expect(isDemoName("notes.zst")).toBe(false);
  });

  it("guesses when the match started, never in the future", () => {
    const end = Date.parse("2026-10-25T21:00:00Z");
    expect(guessPlayedAt(end, end + 1000).toISOString()).toBe("2026-10-25T20:15:00.000Z");
    expect(guessPlayedAt(end + 3_600_000, end).toISOString()).toBe("2026-10-25T20:15:00.000Z");
  });

  it("goes to and from a datetime-local value in the browser's zone", () => {
    const date = new Date(2026, 9, 25, 20, 5);
    expect(toLocalInput(date)).toBe("2026-10-25T20:05");
    expect(fromLocalInput("2026-10-25T20:05")).toBe(date.toISOString());
    expect(fromLocalInput("")).toBeNull();
    expect(fromLocalInput("25/10/2026")).toBeNull();
  });

  it("reads why a send failed", () => {
    expect(sendError(422, '{"detail":{"reason":"not_a_demo"}}')).toBe("not_a_demo");
    expect(sendError(429, '{"detail":{"reason":"busy"}}')).toBe("busy");
    expect(sendError(429, '{"detail":{"reason":"quota"}}')).toBe("quota");
    expect(sendError(422, '{"detail":{"field":"played_at"}}')).toBe("date");
    expect(sendError(413, "")).toBe("too_large");
    expect(sendError(507, '{"detail":{"reason":"disk_full"}}')).toBe("disk_full");
    expect(sendError(503, '{"detail":"uploads are off here"}')).toBe("off");
    expect(sendError(502, '{"detail":"the API did not answer"}')).toBe("network");
    expect(sendError(0, "")).toBe("network");
    expect(sendError(500, "oops")).toBe("unknown");
  });
});
