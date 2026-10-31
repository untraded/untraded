// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// What the consent text says about the instance that runs the site: who operates it, where it is
// hosted, how long raw demos stay. These depend on each instance, so they come from the site's
// environment, never from the code (README, compose.yaml).

export interface Operator {
  /** `UNTRADED_OPERATOR_NAME`: the data controller. */
  name: string | null;
  /** `UNTRADED_OPERATOR_EMAIL`: where players write to use their rights. */
  email: string | null;
  /** `UNTRADED_HOSTING`: where the data lives, e.g. "Oracle Cloud, Frankfurt (EU)". */
  hosting: string | null;
  /** `UNTRADED_DEMO_RETENTION_DAYS`, as the worker reads it: unset keeps raw demos, 0 deletes
   * them once parsed. */
  retentionDays: number | null;
}

function text(value: string | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function operator(env: Record<string, string | undefined> = process.env): Operator {
  const days = text(env.UNTRADED_DEMO_RETENTION_DAYS);
  const parsed = days === null ? null : Number(days);
  return {
    name: text(env.UNTRADED_OPERATOR_NAME),
    email: text(env.UNTRADED_OPERATOR_EMAIL),
    hosting: text(env.UNTRADED_HOSTING),
    retentionDays: parsed !== null && Number.isInteger(parsed) && parsed >= 0 ? parsed : null,
  };
}

/** Steam's Counter-Strike 2 help page where players create their match history authentication
 * code and find the share code of their last match. */
export const STEAM_CODES_HELP =
  "https://help.steampowered.com/wizard/HelpWithGameIssue/?appid=730&issueid=128";

/** `UNTRADED_DEMO_STEAM_ID`, as the API reads it: set, `/api/auth/demo` opens the demo account
 * read-only and the landing page offers it; unset (the default), no demo. */
export function demoEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return text(env.UNTRADED_DEMO_STEAM_ID) !== null;
}

/** `UNTRADED_DISCORD_URL`: an invitation link to the instance's Discord server, shown to
 * visitors (where to ask for an invitation, follow the news); null hides it. Only `https` links
 * to Discord are kept. */
export function discordUrl(env: Record<string, string | undefined> = process.env): string | null {
  const value = text(env.UNTRADED_DISCORD_URL);
  if (value === null) return null;
  try {
    const url = new URL(value);
    const discord = ["discord.gg", "discord.com", "www.discord.com"].includes(url.hostname);
    return url.protocol === "https:" && discord ? url.toString() : null;
  } catch {
    return null;
  }
}
