// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import {
  LOCALE_COOKIE,
  LOCALES,
  type Locale,
  THEME_COOKIE,
  THEMES,
  TONE_COOKIE,
  TONES,
} from "@/i18n/locale";
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

export async function setTone(formData: FormData): Promise<void> {
  const tone = String(formData.get("tone"));
  if ((TONES as readonly string[]).includes(tone)) {
    (await cookies()).set(TONE_COOKIE, tone, {
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      path: "/",
    });
  }
}

export async function setTheme(formData: FormData): Promise<void> {
  const theme = String(formData.get("theme"));
  if ((THEMES as readonly string[]).includes(theme)) {
    (await cookies()).set(THEME_COOKIE, theme, {
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
      path: "/",
    });
  }
}

/** Useful or not useful, on a priority; voting the same way again takes the vote back. */
export async function vote(formData: FormData): Promise<void> {
  const advice = String(formData.get("advice"));
  const session = String(formData.get("session"));
  const value = Number(formData.get("vote"));
  const current = Number(formData.get("current"));
  if (![1, -1].includes(value) || !/^[0-9a-f-]{36}$/.test(advice)) return;
  await apiPost(`/advice/${advice}/feedback`, { vote: value === current ? 0 : value });
  revalidatePath(`/sessions/${session}`);
}
