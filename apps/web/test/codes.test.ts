// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { codeIssue, placeCodes } from "../src/lib/codes";

const AUTH = "ABCD-EFGHI-JKLM";
const SHARE = "CSGO-AbCdE-fGhIj-KlMnO-pQrSt-UvWxY";

describe("codes", () => {
  it("finds each code in what is pasted, as the API does", () => {
    expect(placeCodes(" abcd-efghi-jklm ", SHARE)).toEqual({ auth_code: AUTH, share_code: SHARE });
    expect(
      placeCodes("ABCD - EFGHI - JKLM", `steam://rungame/730/1/+csgo_download_match%20${SHARE}`),
    ).toEqual({ auth_code: AUTH, share_code: SHARE });
  });

  it("puts two codes pasted the other way round back in place", () => {
    expect(placeCodes(SHARE, AUTH)).toEqual({ auth_code: AUTH, share_code: SHARE });
  });

  it("never reads a piece of a share code as an authentication code", () => {
    // Upper-cased, a share code holds `CSGO-ABCDE-FGHI`, which has the form of an auth code.
    expect(placeCodes(SHARE, SHARE)).toEqual({ auth_code: null, share_code: SHARE });
  });

  it("says when a field holds the other code, or no code at all", () => {
    expect(codeIssue("auth_code", AUTH)).toBeNull();
    expect(codeIssue("auth_code", "")).toBeNull();
    expect(codeIssue("auth_code", SHARE)).toBe("other");
    expect(codeIssue("share_code", AUTH)).toBe("other");
    expect(codeIssue("share_code", SHARE)).toBeNull();
    expect(codeIssue("auth_code", "ABCD-EFGH")).toBe("format");
    expect(codeIssue("share_code", "CSGO-12345")).toBe("format");
  });
});
