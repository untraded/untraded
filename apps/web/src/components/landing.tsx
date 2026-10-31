// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronDown, ExternalLink, LogIn, Play } from "lucide-react";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { setLocale } from "@/app/actions";
import { LogoHorizontal } from "@/components/brand/logo";
import { Choice } from "@/components/choice";
import { buttonVariants } from "@/components/ui/button";
import { LOCALES } from "@/i18n/locale";
import { PUBLIC_API_PATH } from "@/lib/api-path";
import { cn } from "@/lib/cn";

const GITHUB = "https://github.com/untraded/untraded";
const FAQ = ["free", "modes", "faceit", "cheat", "rating", "selfhost"] as const;

/** Screenshots of the site, rendered on invented data (no Valve image): captured at twice a
 * 600 px wide column (with a little of the page around), sharp on high-density screens. Their size keeps the layout still. */
const SHOTS = {
  viewer: { width: 1232, height: 1722 },
  priorities: { width: 1232, height: 732 },
  rating: { width: 1232, height: 578 },
} as const;

function Shot({
  name,
  alt,
  first = false,
}: {
  name: keyof typeof SHOTS;
  alt: string;
  first?: boolean;
}) {
  return (
    // biome-ignore lint/performance/noImgElement: a static screenshot, already the right size
    <img
      src={`/showcase/${name}.webp`}
      alt={alt}
      width={SHOTS[name].width}
      height={SHOTS[name].height}
      loading={first ? "eager" : "lazy"}
      fetchPriority={first ? "high" : "auto"}
      className="h-auto w-full rounded-md border border-border bg-card"
    />
  );
}

function Feature({ title, text, children }: { title: string; text: string; children?: ReactNode }) {
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <h3 className="font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{text}</p>
      {children}
    </article>
  );
}

/**
 * The home page of a visitor who is not signed in: what Untraded does, shown on the site itself
 * (screenshots of invented data), how it works, what happens to the data, a short FAQ, and the
 * ways in: the read-only demo, signing in with Steam, Discord.
 */
export async function Landing({
  status,
  discord,
  demo,
}: {
  /** Sign-in notices and errors, and the invitation request when it applies. */
  status: ReactNode;
  discord: string | null;
  /** Whether this instance opens a demo (`UNTRADED_DEMO_STEAM_ID`): its button, else none. */
  demo: boolean;
}) {
  const t = await getTranslations("landing");
  const home = await getTranslations("home");
  const settings = await getTranslations("settings");
  const actions = (
    <div className="flex flex-wrap items-center gap-2.5">
      {demo && (
        <a href={`${PUBLIC_API_PATH}/auth/demo`} className={cn(buttonVariants(), "gap-1.5")}>
          <Play aria-hidden="true" />
          {t("demo")}
        </a>
      )}
      <a
        href={`${PUBLIC_API_PATH}/auth/steam`}
        className={cn(buttonVariants({ variant: demo ? "outline" : "default" }), "gap-1.5")}
      >
        <LogIn aria-hidden="true" />
        {home("signIn")}
      </a>
      {discord && (
        <a
          href={discord}
          rel="noopener noreferrer"
          target="_blank"
          className="inline-flex h-9 items-center gap-1 px-2 text-sm text-link underline underline-offset-3"
        >
          {home("discordLink")}
          <ExternalLink aria-hidden="true" className="size-3.5" />
        </a>
      )}
    </div>
  );
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-16 pb-10">
      <header className="flex items-center justify-between gap-4">
        <LogoHorizontal className="h-6 w-auto" />
        <span className="sr-only">Untraded</span>
        <Choice
          action={setLocale}
          name="locale"
          label={settings("language")}
          value={await getLocale()}
          options={LOCALES.map((code) => ({ value: code, label: settings(`languages.${code}`) }))}
        />
      </header>

      <section className="grid items-center gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="flex flex-col gap-5">
          <p className="text-sm font-medium text-muted-foreground italic">Never die untraded.</p>
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            {t("title")}
          </h1>
          <p className="max-w-prose text-muted-foreground">{t("lead")}</p>
          {status}
          {actions}
          <p className="text-xs text-muted-foreground">{t(demo ? "betaNote" : "betaOnly")}</p>
        </div>
        <Shot name="viewer" alt={t("shots.viewer")} first />
      </section>

      <section aria-labelledby="what" className="flex flex-col gap-5">
        <h2 id="what" className="text-xl font-semibold">
          {t("what.title")}
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Feature title={t("what.priorities")} text={t("what.prioritiesText")}>
            <Shot name="priorities" alt={t("shots.priorities")} />
          </Feature>
          <Feature title={t("what.rating")} text={t("what.ratingText")}>
            <Shot name="rating" alt={t("shots.rating")} />
          </Feature>
          <Feature title={t("what.viewer")} text={t("what.viewerText")} />
          <Feature title={t("what.formulas")} text={t("what.formulasText")}>
            <Link href="/formulas" className="text-sm text-link underline underline-offset-3">
              {t("what.formulasLink")}
            </Link>
          </Feature>
        </div>
      </section>

      <section aria-labelledby="how" className="flex flex-col gap-5">
        <h2 id="how" className="text-xl font-semibold">
          {t("how.title")}
        </h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {(["premier", "upload", "session"] as const).map((step, i) => (
            <li
              key={step}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4"
            >
              <span className="grid size-6 place-items-center rounded-[3px] bg-foreground text-xs font-semibold text-background">
                {i + 1}
              </span>
              <h3 className="font-semibold">{t(`how.${step}`)}</h3>
              <p className="text-sm text-muted-foreground">{t(`how.${step}Text`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="data" className="flex flex-col gap-4">
        <h2 id="data" className="text-xl font-semibold">
          {t("data.title")}
        </h2>
        <ul className="grid gap-4 md:grid-cols-3">
          {(["private", "erase", "open"] as const).map((item) => (
            <li key={item} className="flex flex-col gap-1.5">
              <h3 className="font-semibold">{t(`data.${item}`)}</h3>
              <p className="text-sm text-muted-foreground">{t(`data.${item}Text`)}</p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="faq" className="flex flex-col gap-3">
        <h2 id="faq" className="text-xl font-semibold">
          {t("faq.title")}
        </h2>
        <div className="flex flex-col gap-2">
          {FAQ.map((item) => (
            <details key={item} className="group rounded-lg border border-border bg-card">
              <summary className="flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-4 py-3 font-medium hover:bg-muted [&::-webkit-details-marker]:hidden">
                <ChevronDown
                  aria-hidden="true"
                  className="size-4 -rotate-90 text-muted-foreground transition-transform group-open:rotate-0"
                />
                {t(`faq.${item}`)}
              </summary>
              <p className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
                {t(`faq.${item}Answer`)}
              </p>
            </details>
          ))}
        </div>
      </section>

      <section className="flex flex-col items-start gap-4 rounded-lg border border-border bg-card p-6">
        <h2 className="text-xl font-semibold">{t("end.title")}</h2>
        {demo && <p className="text-sm text-muted-foreground">{t("end.text")}</p>}
        {actions}
      </section>

      <footer className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>{t("footer")}</span>
        <a
          href={GITHUB}
          rel="noopener noreferrer"
          target="_blank"
          className="underline underline-offset-3"
        >
          GitHub
        </a>
      </footer>
    </div>
  );
}
