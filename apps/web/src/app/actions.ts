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
import { apiPost, apiSend, refusedField, SESSION_COOKIE } from "@/lib/api";

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

/** Where a form goes once it is done: one of the site's own pages only. */
function next(formData: FormData, fallback: string): string {
  const target = String(formData.get("next") ?? "");
  return target.startsWith("/") && !target.startsWith("//") ? target : fallback;
}

/**
 * Gives (or changes) the player's consent to the current text: box 1 (`analysis`) is required to
 * take part, box 2 (`research_corpus`) is optional. A 409 means the text changed meanwhile.
 */
export async function giveConsent(formData: FormData): Promise<void> {
  const result = await apiSend("/me/consent", "POST", {
    text_version: String(formData.get("text_version")),
    analysis: formData.get("analysis") === "on",
    research_corpus: formData.get("research_corpus") === "on",
  });
  if (!result.ok) {
    redirect(`/welcome?error=${result.status === 409 ? "version" : "failed"}`);
  }
  revalidatePath("/", "layout");
  redirect(next(formData, "/welcome"));
}

/** Withdraws the player's consent: the collector stops following their matches. */
export async function withdrawConsent(formData: FormData): Promise<void> {
  await apiSend("/me/consent", "POST", {
    text_version: String(formData.get("text_version")),
    analysis: false,
    research_corpus: false,
  });
  revalidatePath("/", "layout");
  redirect("/settings");
}

export type CodesState = {
  error: "auth_code" | "share_code" | "consent" | "unavailable" | "failed" | null;
  auth_code: string;
  share_code: string;
};

/** Gives the two codes the collector needs. Steam checks them first: a refused field comes back
 * to its input, with what the player typed. */
export async function giveCodes(_: CodesState, formData: FormData): Promise<CodesState> {
  const codes = {
    auth_code: String(formData.get("auth_code") ?? "").trim(),
    share_code: String(formData.get("share_code") ?? "").trim(),
  };
  const result = await apiSend("/me/source", "PUT", codes);
  if (!result.ok) {
    const field = refusedField(result);
    const error =
      field === "auth_code" || field === "share_code"
        ? field
        : result.status === 409
          ? "consent"
          : result.status === 503
            ? "unavailable"
            : "failed";
    return { error, ...codes };
  }
  revalidatePath("/", "layout");
  redirect(next(formData, "/"));
}
