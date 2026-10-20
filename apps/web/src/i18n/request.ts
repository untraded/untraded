// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { LOCALE_COOKIE, pickLocale } from "./locale";

// No locale in the URL: the language comes from a cookie or the browser.
export default getRequestConfig(async () => {
  const locale = pickLocale(
    (await cookies()).get(LOCALE_COOKIE)?.value,
    (await headers()).get("accept-language"),
  );
  return { locale, messages: (await import(`../../messages/${locale}.json`)).default };
});
