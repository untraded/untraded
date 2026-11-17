// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { Dashboard } from "@/components/dashboard";
import { Landing } from "@/components/landing";
import { buttonVariants } from "@/components/ui/button";
import { pickTone, SPACE_COOKIE, TONE_COOKIE } from "@/i18n/locale";
import { getMe, PUBLIC_API_PATH } from "@/lib/api";
import { onboardingStep } from "@/lib/onboarding";
import { demoEnabled, discordUrl } from "@/lib/site";
import { PERSONAL_SPACE, rememberedTeam } from "@/lib/space";
import { teamHref, teamsOf } from "@/lib/teams";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ signin?: string; erased?: string; space?: string }>;
}) {
  const me = await getMe();
  if (me) {
    const [{ space }, store] = await Promise.all([searchParams, cookies()]);
    // An invited player gives their consent and their codes first; a team member, who came in by
    // a team's link, needs the consent only (the codes stay offered, optional).
    const step = onboardingStep(me);
    if (step === "consent") redirect("/welcome");
    // Back to the team last opened (after signing in, or from the logo), unless the player chose
    // their own space in the switch (`?space=personal`).
    const teams = teamsOf(me).map((w) => w.slug);
    const team =
      space === PERSONAL_SPACE ? null : rememberedTeam(store.get(SPACE_COOKIE)?.value, teams);
    if (team && !me.demo) redirect(teamHref(team));
    if (step !== null && teams.length === 0) redirect("/welcome");
    return <Dashboard me={me} tone={pickTone(store.get(TONE_COOKIE)?.value)} />;
  }
  const t = await getTranslations("home");
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
  const status = (
    <>
      {notice && (
        <p role="status" className="rounded border border-border bg-card px-4 py-3 text-sm">
          {notice}
        </p>
      )}
      {problem && (
        <p role="alert" className="rounded border border-loss/40 bg-loss/10 px-4 py-3 text-sm">
          {problem}
        </p>
      )}
      {signin === "not_invited" && (
        // A plain form: the API records the request with its signed cookie, then comes back here.
        <form
          method="post"
          action={`${PUBLIC_API_PATH}/auth/invitation-request`}
          className="flex flex-col items-start gap-2"
        >
          <button type="submit" className={buttonVariants()}>
            {t("requestInvite")}
          </button>
          <p className="max-w-md text-xs text-muted-foreground">{t("requestLead")}</p>
        </form>
      )}
    </>
  );
  return <Landing status={status} discord={discord} demo={demoEnabled()} />;
}
