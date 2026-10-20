// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { LogOut } from "lucide-react";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { setLocale, setTheme, setTone, signOut } from "@/app/actions";
import { Choice } from "@/components/choice";
import { Button } from "@/components/ui/button";
import {
  LOCALES,
  pickTheme,
  pickTone,
  THEME_COOKIE,
  THEMES,
  TONE_COOKIE,
  TONES,
} from "@/i18n/locale";
import { getMe } from "@/lib/api";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("settings"))("title") };
}

export default async function Settings() {
  const me = await getMe();
  if (!me) redirect("/");
  const t = await getTranslations("settings");
  const advice = await getTranslations("advice");
  const store = await cookies();
  return (
    <section className="max-w-2xl">
      <h1 className="text-2xl font-semibold">{t("title")}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{t("lead")}</p>
      <div className="mt-6 border-t border-line-soft">
        <Row title={t("tone")} hint={t("toneHint")}>
          <Choice
            action={setTone}
            name="tone"
            label={t("tone")}
            value={pickTone(store.get(TONE_COOKIE)?.value)}
            options={TONES.map((tone) => ({ value: tone, label: advice(tone) }))}
          />
        </Row>
        <Row title={t("language")} hint={t("languageHint")}>
          <Choice
            action={setLocale}
            name="locale"
            label={t("language")}
            value={await getLocale()}
            options={LOCALES.map((code) => ({ value: code, label: t(`languages.${code}`) }))}
          />
        </Row>
        <Row title={t("theme")} hint={t("themeHint")}>
          <Choice
            action={setTheme}
            name="theme"
            label={t("theme")}
            value={pickTheme(store.get(THEME_COOKIE)?.value)}
            options={THEMES.map((theme) => ({ value: theme, label: t(`themes.${theme}`) }))}
          />
        </Row>
        <Row title={t("account")} hint={t("signedInAs", { name: me.display_name })}>
          <form action={signOut}>
            <Button type="submit" variant="outline">
              <LogOut data-icon="inline-start" aria-hidden="true" />
              {t("signOut")}
            </Button>
          </form>
        </Row>
      </div>
    </section>
  );
}

function Row({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-line-soft py-4">
      <div className="min-w-0">
        <h2 className="font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{hint}</p>
      </div>
      {children}
    </div>
  );
}
