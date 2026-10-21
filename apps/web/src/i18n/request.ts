// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { LOCALE_COOKIE, pickLocale } from "./locale";
import { pickTimeZone, TIME_ZONE_COOKIE } from "./time-zone";

// No locale in the URL: the language comes from a cookie or the browser.
export default getRequestConfig(async () => {
  const store = await cookies();
  const locale = pickLocale(
    store.get(LOCALE_COOKIE)?.value,
    (await headers()).get("accept-language"),
  );
  // Dates and times render on the server: in the player's time zone, not the container's.
  const timeZone = pickTimeZone(store.get(TIME_ZONE_COOKIE)?.value, process.env.UNTRADED_TIME_ZONE);
  return { locale, timeZone, messages: (await import(`../../messages/${locale}.json`)).default };
});
