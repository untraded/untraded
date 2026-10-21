// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { LogOut } from "lucide-react";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { giveConsent, setLocale, setTheme, setTone, signOut, withdrawConsent } from "@/app/actions";
import { Choice } from "@/components/choice";
import { CodesForm } from "@/components/codes-form";
import { codesLabels } from "@/components/codes-labels";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { ConsentText } from "@/components/consent-text";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  LOCALES,
  pickTheme,
  pickTone,
  THEME_COOKIE,
  THEMES,
  TONE_COOKIE,
  TONES,
} from "@/i18n/locale";
import { getMe, type Me } from "@/lib/api";
import { cn } from "@/lib/cn";
import { dateTime } from "@/lib/format";

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
      </div>
      <ConsentSection me={me} />
      <FollowSection me={me} />
      <div className="border-t border-line-soft">
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

/** The player's consent: read the text they agreed to, change box 2, or withdraw it. */
async function ConsentSection({ me }: { me: Me }) {
  const t = await getTranslations("settings");
  const locale = (await getLocale()) as "en" | "fr";
  const timeZone = await getTimeZone();
  const { consent } = me;
  const current = consent?.analysis && consent.text_version === me.consent_version;
  const status = !consent
    ? t("consentNone")
    : !consent.analysis
      ? t("consentWithdrawn")
      : consent.text_version !== me.consent_version
        ? t("consentOutdated")
        : t("consentGiven", {
            date: dateTime(consent.recorded_at, locale, timeZone),
            version: consent.text_version,
          });
  const segment =
    "h-7 rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:text-foreground aria-pressed:bg-muted aria-pressed:font-medium aria-pressed:text-foreground";
  return (
    <section className="mt-8 flex flex-col gap-3 border-t border-line-soft pt-5">
      <h2 className="text-lg font-semibold">{t("consentTitle")}</h2>
      <p className="text-sm text-muted-foreground">{status}</p>
      {!current ? (
        <Link href="/welcome" className={cn(buttonVariants(), "w-fit")}>
          {consent && !consent.analysis ? t("giveAgain") : t("readText")}
        </Link>
      ) : (
        <>
          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">
              {t("readText")}
            </summary>
            <div className="border-t border-line-soft p-4">
              <ConsentText version={consent.text_version} />
            </div>
          </details>
          <form
            action={giveConsent}
            className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-line-soft py-3"
          >
            <input type="hidden" name="text_version" value={consent.text_version} />
            <input type="hidden" name="analysis" value="on" />
            <input type="hidden" name="next" value="/settings" />
            <div className="min-w-0">
              <p className="font-semibold">{t("corpus")}</p>
              <p className="text-sm text-muted-foreground">{t("corpusHint")}</p>
            </div>
            <fieldset className="m-0 inline-flex shrink-0 rounded-md border border-border bg-card p-0.5">
              <legend className="sr-only">{t("corpus")}</legend>
              {(["on", "off"] as const).map((value) => (
                <button
                  key={value}
                  type="submit"
                  name="research_corpus"
                  value={value}
                  aria-pressed={consent.research_corpus === (value === "on")}
                  className={segment}
                >
                  {t(value === "on" ? "yes" : "no")}
                </button>
              ))}
            </fieldset>
          </form>
          <form action={withdrawConsent} className="flex flex-col items-start gap-2">
            <input type="hidden" name="text_version" value={me.consent_version} />
            <p className="max-w-prose text-sm text-muted-foreground">{t("withdrawHint")}</p>
            <ConfirmSubmit
              label={t("withdraw")}
              question={t("withdrawConfirm")}
              confirm={t("confirm")}
              cancel={t("cancel")}
            />
          </form>
        </>
      )}
    </section>
  );
}

/** How the collector follows the player's matches, and their codes again when it fails. */
async function FollowSection({ me }: { me: Me }) {
  const t = await getTranslations("settings");
  const locale = (await getLocale()) as "en" | "fr";
  const timeZone = await getTimeZone();
  const { source } = me;
  const status = !source
    ? t("followNone")
    : !source.enabled
      ? t("followPaused")
      : source.last_success_at
        ? t("followOn", { date: dateTime(source.last_success_at, locale, timeZone) })
        : t("followOnNever");
  const error = source?.last_error;
  return (
    <section className="mt-8 flex flex-col gap-3 border-t border-line-soft pt-5">
      <h2 className="text-lg font-semibold">{t("followTitle")}</h2>
      <p className="text-sm text-muted-foreground">{status}</p>
      {error && (
        <div className="flex flex-col gap-4 rounded-lg border border-destructive/40 bg-card p-4">
          <p role="status" className="max-w-prose text-sm">
            {error === "403"
              ? t("error403")
              : error === "412"
                ? t("error412")
                : t("errorOther", { error })}
          </p>
          <h3 className="font-semibold">{t("codesAgain")}</h3>
          <CodesForm labels={await codesLabels()} next="/settings" />
        </div>
      )}
    </section>
  );
}
