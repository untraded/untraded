// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import {
  moved,
  parseTags,
  reviewError,
  reviewHref,
  reviewRoundHref,
  roundParam,
  shownError,
  viewerHref,
} from "@/lib/review";

describe("parseTags", () => {
  it("splits on commas, collapses blank space and keeps each tag once whatever its case", () => {
    expect(parseTags(" Retake ,  B   site,retake,, ")).toEqual(["Retake", "B site"]);
  });
  it("reads an empty field as no tag", () => {
    expect(parseTags("  ,  ")).toEqual([]);
  });
});

describe("roundParam", () => {
  it("takes a round from 1 to 99 only", () => {
    expect(roundParam("7")).toBe(7);
    expect(roundParam("0")).toBeNull();
    expect(roundParam("100")).toBeNull();
    expect(roundParam("3a")).toBeNull();
    expect(roundParam(undefined)).toBeNull();
  });
});

describe("addresses", () => {
  it("encodes what comes from the API", () => {
    expect(reviewRoundHref("north", "a/b", 4)).toBe("/teams/north/matches/a%2Fb?round=4#round-4");
    expect(viewerHref("m 1", 4)).toBe("/matches/m%201/rounds/4");
    expect(viewerHref("m", 4, 3250)).toBe("/matches/m/rounds/4?t=3250");
    expect(viewerHref("m", 4, 1.5)).toBe("/matches/m/rounds/4");
    expect(reviewHref("north")).toBe("/teams/north/review");
    expect(reviewHref("north", "x&y")).toBe("/teams/north/review?playlist=x%26y");
  });
});

describe("errors", () => {
  it("names a missing match, round, comment or playlist alike", () => {
    for (const code of [
      "match_not_found",
      "round_not_found",
      "comment_not_found",
      "playlist_not_found",
    ]) {
      expect(reviewError(code, 404)).toBe("gone");
    }
  });
  it("reads the demo's refusal, unknown codes and statuses", () => {
    expect(reviewError("demo", 403)).toBe("read_only");
    expect(reviewError("tag_limit", 409)).toBe("tag_limit");
    expect(reviewError(null, 403)).toBe("forbidden");
    expect(reviewError("whatever", 500)).toBe("failed");
  });
  it("shows only the codes it knows", () => {
    expect(shownError("comment_invalid")).toBe("comment_invalid");
    expect(shownError("<script>")).toBe("failed");
    expect(shownError(undefined)).toBeNull();
  });
});

describe("moved", () => {
  const items = [
    { match_id: "a", round: 1, tags: [] },
    { match_id: "b", round: 2, tags: [] },
    { match_id: "a", round: 3, tags: [] },
  ];
  it("moves a round by one place, and only its reference", () => {
    expect(moved(items, 1, -1)).toEqual([
      { match_id: "b", round: 2 },
      { match_id: "a", round: 1 },
      { match_id: "a", round: 3 },
    ]);
    expect(moved(items, 1, 1).map((r) => r.round)).toEqual([1, 3, 2]);
  });
  it("leaves the order as it is at either end", () => {
    expect(moved(items, 0, -1).map((r) => r.round)).toEqual([1, 2, 3]);
    expect(moved(items, 2, 1).map((r) => r.round)).toEqual([1, 2, 3]);
  });
});
