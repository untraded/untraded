// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { LOCALE_COOKIE, LOCALES, type Locale } from "@/i18n/locale";
import { apiPost, SESSION_COOKIE } from "@/lib/api";

/** Ends the session in the database, then drops the cookie. */
export async function signOut(): Promise<void> {
  await apiPost("/auth/logout");
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/");
}

export async function setLocale(formData: FormData): Promise<void> {
  const locale = String(formData.get("locale"));
  if ((LOCALES as readonly string[]).includes(locale)) {
    (await cookies()).set(LOCALE_COOKIE, locale as Locale, {
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      path: "/",
    });
  }
}
