// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

const ENDPOINT = "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1";

export type NextCodeResult =
  | { kind: "next"; code: string }
  | { kind: "none" } // 202: no newer match yet
  | { kind: "fatal"; status: number; reason: string } // stop and ask the user
  | { kind: "retry"; status: number }; // rate limit or server error

interface ApiResponse {
  result?: { nextcode?: string };
}

/** One call to GetNextMatchSharingCode. See CLAUDE.md for the status code semantics. */
export async function nextShareCode(params: {
  apiKey: string;
  steamId: string;
  authCode: string;
  knownCode: string;
}): Promise<NextCodeResult> {
  const url = new URL(ENDPOINT);
  url.searchParams.set("key", params.apiKey);
  url.searchParams.set("steamid", params.steamId);
  url.searchParams.set("steamidkey", params.authCode);
  url.searchParams.set("knowncode", params.knownCode);

  const response = await fetch(url, { signal: AbortSignal.timeout(15_000) });
  switch (response.status) {
    case 200: {
      const body = (await response.json()) as ApiResponse;
      const code = body.result?.nextcode;
      return code && code !== "n/a" ? { kind: "next", code } : { kind: "none" };
    }
    case 202:
      return { kind: "none" };
    case 403:
      return { kind: "fatal", status: 403, reason: "invalid auth code (steamidkey)" };
    case 412:
      return {
        kind: "fatal",
        status: 412,
        reason: "known share code invalid or older than one month: provide a fresh share code",
      };
    default:
      return { kind: "retry", status: response.status };
  }
}
