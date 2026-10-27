// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { LogIn } from "lucide-react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { setLocale } from "@/app/actions";
import { Choice } from "@/components/choice";
import { Dashboard } from "@/components/dashboard";
import { buttonVariants } from "@/components/ui/button";
import { LOCALES, pickTone, TONE_COOKIE } from "@/i18n/locale";
import { getMe, PUBLIC_API_PATH } from "@/lib/api";
import { cn } from "@/lib/cn";
import { onboardingStep } from "@/lib/onboarding";
import { discordUrl } from "@/lib/site";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ signin?: string; erased?: string }>;
}) {
  const me = await getMe();
  if (me) {
    // An invited player gives their consent and their codes first.
    if (onboardingStep(me) !== null) redirect("/welcome");
    return <Dashboard me={me} tone={pickTone((await cookies()).get(TONE_COOKIE)?.value)} />;
  }
  const t = await getTranslations("home");
  const settings = await getTranslations("settings");
  const { signin, erased } = await searchParams;
  const problem =
    signin === "not_invited"
      ? t("notInvited")
      : signin === "failed"
        ? t("failed")
        : signin === "request_expired"
          ? t("requestExpired")
          : null;
  const notice = signin === "requested" ? t("requested") : erased && !problem ? t("erased") : null;
  const discord = discordUrl();
  return (
    <>
      <div className="flex items-center justify-between">
        <span className="font-bold">Untraded</span>
        <Choice
          action={setLocale}
          name="locale"
          label={settings("language")}
          value={await getLocale()}
          options={LOCALES.map((code) => ({ value: code, label: settings(`languages.${code}`) }))}
        />
      </div>
      <section className="mx-auto max-w-2xl py-16 text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("title")}</h1>
        <p className="mt-4 text-muted-foreground">{t("lead")}</p>
        {notice && (
          <p role="status" className="mt-8 rounded border border-border bg-card px-4 py-3 text-sm">
            {notice}
          </p>
        )}
        {problem && (
          <p
            role="alert"
            className="mt-8 rounded border border-loss/40 bg-loss/10 px-4 py-3 text-sm"
          >
            {problem}
          </p>
        )}
        {signin === "not_invited" && (
          // A plain form: the API records the request with its signed cookie, then comes back here.
          <form
            method="post"
            action={`${PUBLIC_API_PATH}/auth/invitation-request`}
            className="mt-6 flex flex-col items-center gap-2"
          >
            <button type="submit" className={buttonVariants()}>
              {t("requestInvite")}
            </button>
            <p className="max-w-md text-xs text-muted-foreground">{t("requestLead")}</p>
          </form>
        )}
        <a
          href={`${PUBLIC_API_PATH}/auth/steam`}
          className={cn(
            buttonVariants({ variant: signin === "not_invited" ? "outline" : "default" }),
            "mt-10",
          )}
        >
          <LogIn data-icon="inline-start" aria-hidden="true" />
          {t("signIn")}
        </a>
        <p className="mt-3 text-xs text-muted-foreground">{t("beta")}</p>
        {discord && (
          <p className="mt-6 text-sm text-muted-foreground">
            {t("discord")}{" "}
            <a
              href={discord}
              rel="noopener noreferrer"
              target="_blank"
              className="font-medium text-foreground underline underline-offset-2 hover:text-primary"
            >
              {t("discordLink")}
            </a>
          </p>
        )}
      </section>
    </>
  );
}
