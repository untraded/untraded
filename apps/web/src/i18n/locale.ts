// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

export const LOCALES = ["en", "fr"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
/** Set by the language switcher; otherwise the browser's languages decide. */
export const LOCALE_COOKIE = "untraded_locale";

function isLocale(value: string): value is Locale {
  return (LOCALES as readonly string[]).includes(value);
}

/** The interface language: the cookie, else the first supported browser language. */
export function pickLocale(cookie: string | undefined, acceptLanguage: string | null): Locale {
  if (cookie && isLocale(cookie)) return cookie;
  const wanted = (acceptLanguage ?? "")
    .split(",")
    .map((part) => {
      const [tag = "", ...params] = part.trim().split(";");
      const q = params.find((p) => p.trim().startsWith("q="));
      return { lang: tag.toLowerCase().split("-")[0] ?? "", q: q ? Number(q.split("=")[1]) : 1 };
    })
    .filter((entry) => entry.lang && !Number.isNaN(entry.q))
    .sort((a, b) => b.q - a.q);
  return wanted.map((entry) => entry.lang).find(isLocale) ?? DEFAULT_LOCALE;
}

export const TONES = ["coach", "analyst"] as const;
export type Tone = (typeof TONES)[number];
/** Coach (direct, prescriptive) by default; analyst gives neutral findings. */
export const TONE_COOKIE = "untraded_tone";

export function pickTone(cookie: string | undefined): Tone {
  return cookie === "analyst" ? "analyst" : "coach";
}

export const THEMES = ["system", "light", "dark"] as const;
export type Theme = (typeof THEMES)[number];
/** Light or dark: the system's by default, or the player's choice in the settings. */
export const THEME_COOKIE = "untraded_theme";

export function pickTheme(cookie: string | undefined): Theme {
  return cookie === "light" || cookie === "dark" ? cookie : "system";
}

/** The sidebar, folded to its icons or not (remembered per browser). */
export const SIDEBAR_COOKIE = "untraded_sidebar";
