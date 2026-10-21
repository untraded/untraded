// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Dates and times render on the server: in the player's time zone, sent by their browser in a
// cookie, else in the instance's (`UNTRADED_TIME_ZONE`), else Paris.

/** Set by the browser on the first visit (`TimeZoneSync`), from `Intl`. */
export const TIME_ZONE_COOKIE = "untraded_tz";
export const DEFAULT_TIME_ZONE = "Europe/Paris";

/** Whether `Intl` knows this IANA time zone (an unknown one would throw when formatting). */
export function isTimeZone(value: string | undefined | null): value is string {
  if (!value || value.length > 64) return false;
  try {
    new Intl.DateTimeFormat("en", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

/** The cookie's time zone if valid, else the instance's if valid, else Paris. */
export function pickTimeZone(cookie: string | undefined, instance: string | undefined): string {
  if (isTimeZone(cookie)) return cookie;
  if (isTimeZone(instance)) return instance;
  return DEFAULT_TIME_ZONE;
}
