// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The two codes a player gives, read as the API reads them (`apps/api`, `onboarding.py`): the
// same patterns, so that the site can tell a wrong format from a code Steam refuses.

/** A whole authentication code (`AAAA-AAAAA-AAAA`), never a piece of a longer code. */
const AUTH_CODE = /(?<![A-Z0-9-])[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{4}(?![A-Z0-9-])/;
/** A share code (`CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`). */
const SHARE_CODE = /CSGO(?:-[A-Za-z0-9]{5}){5}(?![A-Za-z0-9-])/;

export type CodeField = "auth_code" | "share_code";
/** What is wrong with a field before Steam sees it: the other code, or no code at all. */
export type CodeIssue = "other" | "format";

/** The code in what the player pasted: spaces anywhere, or the code inside a longer text. */
function find(pattern: RegExp, text: string): string | null {
  return pattern.exec(text.replace(/\s+/g, ""))?.[0] ?? null;
}

const findAuth = (text: string) => find(AUTH_CODE, text.toUpperCase());
const findShare = (text: string) => find(SHARE_CODE, text);

/** The two codes, put back in place when they were pasted the other way round. */
export function placeCodes(
  authText: string,
  shareText: string,
): { auth_code: string | null; share_code: string | null } {
  const auth = findAuth(authText);
  const share = findShare(shareText);
  if (auth === null && share === null) {
    const swappedAuth = findAuth(shareText);
    const swappedShare = findShare(authText);
    if (swappedAuth && swappedShare) return { auth_code: swappedAuth, share_code: swappedShare };
  }
  return { auth_code: auth, share_code: share };
}

/** What is wrong with one field, as typed: `null` when it holds its code, or is still empty. */
export function codeIssue(field: CodeField, text: string): CodeIssue | null {
  if (text.trim() === "") return null;
  const [own, other] = field === "auth_code" ? [findAuth, findShare] : [findShare, findAuth];
  if (own(text)) return null;
  return other(text) ? "other" : "format";
}
