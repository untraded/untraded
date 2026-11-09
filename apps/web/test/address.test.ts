// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { refusedAddress } from "@/lib/address";

// What FastAPI answers for `/sessions/b1401a08`.
const malformed = {
  detail: [
    {
      type: "uuid_parsing",
      loc: ["path", "session_id"],
      msg: "Input should be a valid UUID",
      input: "b1401a08",
    },
  ],
};

describe("refusedAddress", () => {
  it("is a malformed path parameter", () => {
    expect(refusedAddress(422, malformed)).toBe(true);
  });

  it("is not a refused query or body", () => {
    expect(refusedAddress(422, { detail: [{ loc: ["query", "limit"], msg: "x" }] })).toBe(false);
    expect(refusedAddress(422, { detail: [{ loc: ["body", "vote"], msg: "x" }] })).toBe(false);
    // One wrong path parameter among other errors: still a request the page got wrong.
    expect(
      refusedAddress(422, { detail: [...malformed.detail, { loc: ["query", "limit"] }] }),
    ).toBe(false);
  });

  it("is not another status or shape", () => {
    expect(refusedAddress(500, malformed)).toBe(false);
    expect(refusedAddress(422, { detail: { field: "name" } })).toBe(false);
    expect(refusedAddress(422, { detail: [] })).toBe(false);
    expect(refusedAddress(422, null)).toBe(false);
    expect(refusedAddress(422, "Unprocessable")).toBe(false);
  });
});
