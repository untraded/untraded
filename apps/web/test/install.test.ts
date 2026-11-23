// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import {
  countVisit,
  installState,
  isIos,
  localDay,
  NO_MEMORY,
  parseMemory,
  STRIP_FROM_DAY,
  showsStrip,
} from "../src/lib/install";
import { offlineHtml, offlineVersion } from "../src/lib/offline-page";
import { serviceWorkerSource } from "../src/lib/service-worker";
import { CHROME_DARK, CHROME_LIGHT, themeColor } from "../src/lib/theme-color";

describe("install state", () => {
  it("offers nothing once installed, whatever the browser says", () => {
    expect(installState({ standalone: true, promptable: true, ios: true })).toBe("installed");
  });

  it("replays the browser's offer where there is one, else explains the iPhone's two taps", () => {
    expect(installState({ standalone: false, promptable: true, ios: false })).toBe("prompt");
    expect(installState({ standalone: false, promptable: false, ios: true })).toBe("ios");
    expect(installState({ standalone: false, promptable: false, ios: false })).toBe("unavailable");
  });

  it("tells an iPhone or an iPad, which reports itself as a Mac", () => {
    const iphone =
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1";
    const mac =
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15";
    expect(isIos(iphone, "iPhone", 5)).toBe(true);
    expect(isIos(mac, "MacIntel", 5)).toBe(true);
    expect(isIos(mac, "MacIntel", 0)).toBe(false);
    expect(isIos("Mozilla/5.0 (Linux; Android 15) Chrome/140.0", "Linux armv8l", 5)).toBe(false);
  });
});

describe("install strip", () => {
  it("counts a day once, however many pages are opened", () => {
    const first = countVisit(NO_MEMORY, "2026-11-20");
    expect(first).toEqual({ days: 1, last: "2026-11-20", dismissed: false });
    expect(countVisit(first, "2026-11-20")).toBe(first);
    expect(countVisit(first, "2026-11-22").days).toBe(2);
  });

  it("waits for the third day, and never comes back once closed", () => {
    const early = { days: STRIP_FROM_DAY - 1, last: "2026-11-22", dismissed: false };
    const due = { ...early, days: STRIP_FROM_DAY };
    expect(showsStrip("prompt", early)).toBe(false);
    expect(showsStrip("prompt", due)).toBe(true);
    expect(showsStrip("ios", due)).toBe(true);
    expect(showsStrip("prompt", { ...due, dismissed: true })).toBe(false);
  });

  it("shows nothing where nothing can be installed", () => {
    const due = { days: 10, last: "2026-11-22", dismissed: false };
    for (const state of ["unknown", "installed", "unavailable"] as const) {
      expect(showsStrip(state, due)).toBe(false);
    }
  });

  it("reads back only what it wrote", () => {
    expect(parseMemory(null)).toEqual(NO_MEMORY);
    expect(parseMemory("{not json")).toEqual(NO_MEMORY);
    expect(parseMemory("[]")).toEqual(NO_MEMORY);
    expect(parseMemory('{"days":3,"last":"2026-11-22","dismissed":true}')).toEqual({
      days: 3,
      last: "2026-11-22",
      dismissed: true,
    });
    expect(parseMemory('{"days":-4,"last":"<script>","dismissed":"yes"}')).toEqual(NO_MEMORY);
  });

  it("names the local day", () => {
    expect(localDay(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
  });
});

describe("offline page and service worker", () => {
  it("holds both languages and nothing that varies", () => {
    const html = offlineHtml();
    expect(html).toContain('data-l="en"');
    expect(html).toContain('data-l="fr"');
    expect(html).toContain("No connection");
    expect(html).toContain("Pas de réseau");
    expect(offlineHtml()).toBe(html);
    expect(offlineVersion()).toMatch(/^[0-9a-f]{12}$/);
  });

  it("answers page loads only, and stores no response but the offline page", () => {
    const source = serviceWorkerSource("abc123");
    expect(source).toContain('const CACHE = "untraded-offline-abc123";');
    expect(source).toContain('request.mode !== "navigate"');
    expect(source).not.toMatch(/cache\.put|\.addAll\(/);
    expect(source.match(/cache\.add\(/g)).toHaveLength(1);
  });

  it("colours the browser's bar like the chrome", () => {
    expect(themeColor("dark")).toBe(CHROME_DARK);
    expect(themeColor("light")).toBe(CHROME_LIGHT);
    expect(themeColor("system")).toEqual([
      { media: "(prefers-color-scheme: light)", color: CHROME_LIGHT },
      { media: "(prefers-color-scheme: dark)", color: CHROME_DARK },
    ]);
  });
});
