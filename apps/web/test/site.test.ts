// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { demoEnabled, discordUrl, operator } from "../src/lib/site";

describe("operator", () => {
  it("reads the instance's settings, empty ones as unset", () => {
    const found = operator({
      UNTRADED_OPERATOR_NAME: " Ada ",
      UNTRADED_OPERATOR_EMAIL: "",
      UNTRADED_DEMO_RETENTION_DAYS: "7",
    });
    expect(found).toEqual({ name: "Ada", email: null, hosting: null, retentionDays: 7 });
  });

  it("keeps demos when the retention is unset or not a number of days", () => {
    expect(operator({}).retentionDays).toBeNull();
    expect(operator({ UNTRADED_DEMO_RETENTION_DAYS: "soon" }).retentionDays).toBeNull();
    expect(operator({ UNTRADED_DEMO_RETENTION_DAYS: "0" }).retentionDays).toBe(0);
  });
});

describe("discordUrl", () => {
  it("keeps an https link to Discord, nothing else", () => {
    expect(discordUrl({ UNTRADED_DISCORD_URL: " https://discord.gg/abc " })).toBe(
      "https://discord.gg/abc",
    );
    expect(discordUrl({})).toBeNull();
    expect(discordUrl({ UNTRADED_DISCORD_URL: "http://discord.gg/abc" })).toBeNull();
    expect(discordUrl({ UNTRADED_DISCORD_URL: "https://evil.test/discord" })).toBeNull();
    expect(discordUrl({ UNTRADED_DISCORD_URL: "not a url" })).toBeNull();
  });
});

describe("demoEnabled", () => {
  it("follows the API's demo account", () => {
    expect(demoEnabled({ UNTRADED_DEMO_STEAM_ID: "76561190000100001" })).toBe(true);
    expect(demoEnabled({ UNTRADED_DEMO_STEAM_ID: " " })).toBe(false);
    expect(demoEnabled({})).toBe(false);
  });
});
