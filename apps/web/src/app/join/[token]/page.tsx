// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { LogIn, OctagonX } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { acceptInvitation } from "@/app/teams/actions";
import { LogoHorizontal } from "@/components/brand/logo";
import { roleLabel } from "@/components/teams/role-label";
import { Button, buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { findInvitation, getMe, PUBLIC_API_PATH } from "@/lib/api";
import { cn } from "@/lib/cn";
import { day } from "@/lib/format";
import { onboardingStep } from "@/lib/onboarding";
import { joinPath, validToken } from "@/lib/teams";

type Params = {
  params: Promise<{ token: string }>;
  searchParams: Promise<{ error?: string }>;
};

/** The token is in the address: no search engine keeps it, and no other site learns it from a
 * link followed from here. */
export async function generateMetadata(): Promise<Metadata> {
  return {
    title: (await getTranslations("teams"))("join.title"),
    robots: { index: false, follow: false },
    referrer: "no-referrer",
  };
}

const ERRORS = ["invitation_invalid", "already_member", "consent_required", "read_only"] as const;

/**
 * Where an invitation link leads: the team and the role it gives, then what the visitor still has
 * to do. Opening the link joins nothing: signed out, they sign in with Steam (the token goes along
 * and brings them back here); without a current consent, they read it first; then a button joins.
 */
export default async function Join({ params, searchParams }: Params) {
  const [{ token }, query, t, locale] = await Promise.all([
    params,
    searchParams,
    getTranslations("teams"),
    getLocale(),
  ]);
  const preview = validToken(token) ? await findInvitation(token) : null;
  if (!preview) {
    return (
      <section className="mx-auto flex max-w-xl flex-col gap-4 py-6">
        <Panel title={t("join.invalidTitle")} bodyClassName="flex flex-col gap-3">
          <p className="flex items-start gap-2 text-[0.9375rem]">
            <OctagonX aria-hidden="true" className="mt-1 size-4 shrink-0 text-destructive" />
            {t("join.invalidText")}
          </p>
          <Link href="/" className={cn(buttonVariants({ variant: "outline" }), "w-fit")}>
            {t("join.home")}
          </Link>
        </Panel>
      </section>
    );
  }
  const me = await getMe();
  const team = preview.team_name;
  const error = ERRORS.find((e) => e === query.error) ?? (query.error ? "failed" : null);
  const already = error === "already_member";
  let next: ReactNode;
  if (!me) {
    next = (
      <>
        <p className="text-sm text-muted-foreground">{t("join.signInLead")}</p>
        <a
          href={`${PUBLIC_API_PATH}/auth/steam?team_invite=${encodeURIComponent(token)}`}
          className={cn(buttonVariants(), "w-fit")}
        >
          <LogIn data-icon="inline-start" aria-hidden="true" />
          {t("join.signIn")}
        </a>
      </>
    );
  } else if (me.demo) {
    next = <p className="text-sm text-muted-foreground">{t("join.demo")}</p>;
  } else if (already) {
    next = (
      <>
        <p className="text-sm text-muted-foreground">{t("join.already")}</p>
        <Link href="/" className={cn(buttonVariants({ variant: "outline" }), "w-fit")}>
          {t("join.home")}
        </Link>
      </>
    );
  } else if (onboardingStep(me) === "consent") {
    next = (
      <>
        <p className="max-w-prose text-sm text-muted-foreground">{t("join.consentLead")}</p>
        <Link
          href={`/welcome?next=${encodeURIComponent(joinPath(token))}`}
          className={cn(buttonVariants(), "w-fit")}
        >
          {t("join.consentButton")}
        </Link>
      </>
    );
  } else {
    next = (
      <form action={acceptInvitation} className="flex flex-col items-start gap-2.5">
        <input type="hidden" name="token" value={token} />
        <p className="max-w-prose text-sm text-muted-foreground">{t("join.lead")}</p>
        <Button type="submit">{t("join.joinButton", { team })}</Button>
      </form>
    );
  }
  return (
    <section className="mx-auto flex max-w-xl flex-col gap-4 py-6">
      {/* Signed out, there is no rail: the logo says where the link led. */}
      {!me && (
        <Link href="/" aria-label="Untraded" className="flex h-8 w-fit items-center">
          <LogoHorizontal className="h-5 w-auto" />
        </Link>
      )}
      <Panel title={t("join.title")} bodyClassName="flex flex-col gap-4 sm:px-5 sm:py-4">
        <div className="flex flex-col gap-1">
          <p className="text-lg font-semibold break-words">{t("join.invited", { team })}</p>
          <p className="text-sm">{t("join.roleLine", { role: roleLabel(t, preview.role) })}</p>
          <p className="text-[0.8125rem] text-muted-foreground">
            {t("join.expires", { date: day(preview.expires_at.slice(0, 10), locale as Locale) })}
          </p>
        </div>
        {error && error !== "already_member" && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive"
          >
            <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t(`errors.${error}`)}
          </p>
        )}
        <div className="flex flex-col gap-2.5 border-t border-line-soft pt-4">{next}</div>
      </Panel>
    </section>
  );
}
