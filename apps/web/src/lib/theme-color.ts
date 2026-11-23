// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Viewport } from "next";
import type { Theme } from "@/i18n/locale";

/** The dark chrome (rail, phone top bar) in each theme: `--chrome` in `globals.css`. */
export const CHROME_LIGHT = "#1b1f24";
export const CHROME_DARK = "#101213";

/**
 * The browser's bar colour (`<meta name="theme-color">`), matched to the chrome below it: the
 * player's theme when they chose one in the settings, else one colour per system theme.
 */
export function themeColor(theme: Theme): Viewport["themeColor"] {
  if (theme === "light") return CHROME_LIGHT;
  if (theme === "dark") return CHROME_DARK;
  return [
    { media: "(prefers-color-scheme: light)", color: CHROME_LIGHT },
    { media: "(prefers-color-scheme: dark)", color: CHROME_DARK },
  ];
}
