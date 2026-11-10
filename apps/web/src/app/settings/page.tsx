// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { LogOut } from "lucide-react";
import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getLocale, getTimeZone, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import {
  eraseMe,
  giveConsent,
  setLocale,
  setTheme,
  setTone,
  signOut,
  withdrawConsent,
} from "@/app/actions";
import { Choice } from "@/components/choice";
import { CodesForm } from "@/components/codes-form";
import { codesLabels } from "@/components/codes-labels";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { ConsentText } from "@/components/consent-text";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
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

/**
 * The player's settings, one panel per subject: the preferences this browser keeps, then (not in
 * the read-only demo) their consent and how their matches are followed, their Steam account, and
 * last the erasure, which the consent panel points down to. No context bar: the page is about no
 * session or match, and has no figures to keep in view.
 */
export default async function Settings({
  searchParams,
}: {
  searchParams: Promise<{ erase?: string }>;
}) {
  const [me, t, advice, store, locale, params] = await Promise.all([
    getMe(),
    getTranslations("settings"),
    getTranslations("advice"),
    cookies(),
    getLocale(),
    searchParams,
  ]);
  if (!me) redirect("/");
  const demo = await getTranslations("demo");
  return (
    <section className="flex max-w-3xl flex-col gap-3.5">
      <h1 className="mb-2 text-2xl font-semibold md:text-[1.75rem]">{t("title")}</h1>
      {/* "Saved in this browser" is said of the preferences alone: it sits in their band. */}
      <Panel title={t("preferences")} aside={t("lead")} flush>
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
            value={locale}
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
      </Panel>
      {me.demo ? (
        <p className="rounded-md border border-dashed border-border bg-card px-3.5 py-2.5 text-sm text-muted-foreground">
          {demo("settings")}
        </p>
      ) : (
        <>
          <ConsentPanel me={me} />
          <FollowPanel me={me} />
        </>
      )}
      <Panel title={t("account")}>
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <p className="min-w-0 text-sm break-words text-muted-foreground">
            {t("signedInAs", { name: me.display_name })}
          </p>
          <form action={signOut}>
            <Button type="submit" variant="outline">
              <LogOut data-icon="inline-start" aria-hidden="true" />
              {t("signOut")}
            </Button>
          </form>
        </div>
      </Panel>
      {!me.demo && <ErasePanel failed={params.erase === "failed"} />}
    </section>
  );
}

/** One setting in a panel's list: its name and what it does, its control at the right. */
function Row({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5 border-t border-line-soft px-3.5 py-3 first:border-t-0">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-[0.8125rem] text-muted-foreground">{hint}</p>
      </div>
      {children}
    </div>
  );
}

/** The player's consent: read the text they agreed to, change box 2, or withdraw it. */
async function ConsentPanel({ me }: { me: Me }) {
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
    <Panel title={t("consentTitle")} flush>
      <div className="flex flex-col gap-3 px-3.5 py-3">
        <p className="text-sm text-muted-foreground">{status}</p>
        {!current ? (
          <Link href="/welcome" className={cn(buttonVariants(), "w-fit")}>
            {consent && !consent.analysis ? t("giveAgain") : t("readText")}
          </Link>
        ) : (
          <details className="group rounded-md border border-border">
            <summary className="cursor-pointer rounded-md px-3 py-2 text-sm font-medium group-open:rounded-b-none hover:bg-muted">
              {t("readText")}
            </summary>
            <div className="border-t border-line-soft p-4">
              <ConsentText version={consent.text_version} level={3} />
            </div>
          </details>
        )}
      </div>
      {current && (
        <>
          <form
            action={giveConsent}
            className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5 border-t border-line-soft px-3.5 py-3"
          >
            <input type="hidden" name="text_version" value={consent.text_version} />
            <input type="hidden" name="analysis" value="on" />
            <input type="hidden" name="next" value="/settings" />
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">{t("corpus")}</h3>
              <p className="text-[0.8125rem] text-muted-foreground">{t("corpusHint")}</p>
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
          <form
            action={withdrawConsent}
            className="flex flex-col items-start gap-2.5 border-t border-line-soft px-3.5 py-3"
          >
            <input type="hidden" name="text_version" value={me.consent_version} />
            <p className="max-w-prose text-[0.8125rem] text-muted-foreground">
              {t("withdrawHint")}
            </p>
            <ConfirmSubmit
              label={t("withdraw")}
              question={t("withdrawConfirm")}
              confirm={t("confirm")}
              cancel={t("cancel")}
            />
          </form>
        </>
      )}
    </Panel>
  );
}

/** How the collector follows the player's matches, and their codes again when it fails. */
async function FollowPanel({ me }: { me: Me }) {
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
    <Panel title={t("followTitle")} flush>
      <p className="px-3.5 py-3 text-sm text-muted-foreground">{status}</p>
      {error && (
        <div className="flex flex-col gap-4 border-t border-line-soft px-3.5 py-3">
          <p
            role="status"
            className="max-w-prose rounded-md border border-border border-l-[3px] border-l-destructive px-3 py-2 text-sm"
          >
            {error === "403"
              ? t("error403")
              : error === "412"
                ? t("error412")
                : t("errorOther", { error })}
          </p>
          <h3 className="text-sm font-semibold">{t("codesAgain")}</h3>
          <CodesForm labels={await codesLabels()} next="/settings" />
        </div>
      )}
    </Panel>
  );
}

/** The player's right to erasure: what goes, what stays, and that it is final. */
async function ErasePanel({ failed }: { failed: boolean }) {
  const t = await getTranslations("settings");
  const items = Object.keys(t.raw("eraseItems") as Record<string, string>);
  return (
    // A named region, as before: a screen reader can jump to it (`Panel` names none).
    <section aria-label={t("eraseTitle")} className="mt-4">
      <Panel
        title={t("eraseTitle")}
        className="border-destructive/40"
        bodyClassName="flex flex-col gap-3"
      >
        <div className="flex max-w-prose flex-col gap-2 text-sm">
          <p>{t("eraseLead")}</p>
          <ul className="flex list-disc flex-col gap-1 pl-5 marker:text-muted-foreground">
            {items.map((item) => (
              <li key={item}>{t(`eraseItems.${item}`)}</li>
            ))}
          </ul>
          <p className="text-muted-foreground">{t("eraseShared")}</p>
          <p className="font-semibold">{t("eraseFinal")}</p>
        </div>
        {failed && (
          <p role="alert" className="text-sm text-destructive">
            {t("eraseFailed")}
          </p>
        )}
        <form action={eraseMe} className="flex flex-col items-start gap-2">
          <ConfirmSubmit
            label={t("erase")}
            question={t("eraseConfirm")}
            confirm={t("eraseYes")}
            cancel={t("cancel")}
          />
        </form>
      </Panel>
    </section>
  );
}
