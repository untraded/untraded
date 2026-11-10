// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { SearchingCrosshair } from "@/components/searching-crosshair";
import { buttonVariants } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { getMe } from "@/lib/api";
import { discordUrl } from "@/lib/site";

/**
 * The page for an address that leads nowhere: what happened, in a panel, its possible causes and
 * where to go from here (home, and for a signed-in player their matches and sessions).
 */
export default async function NotFound() {
  const [me, t] = await Promise.all([getMe(), getTranslations("notFound")]);
  const discord = discordUrl();
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-5 py-10 sm:py-16">
      <div className="flex items-start gap-4">
        <SearchingCrosshair className="mt-1 size-12 shrink-0 text-foreground" />
        <div className="flex flex-col gap-1">
          <p className="font-mono text-xs text-muted-foreground tabular-nums">{t("tag")}</p>
          <h1 className="text-2xl leading-tight font-semibold">{t("title")}</h1>
          <p className="text-muted-foreground">{t("lead")}</p>
        </div>
      </div>
      <Panel title={t("why")} bodyClassName="flex flex-col gap-4 px-4 py-3.5">
        <ul className="flex list-disc flex-col gap-1.5 pl-4 text-sm leading-relaxed marker:text-muted-foreground">
          <li>{t("reasonLink")}</li>
          <li>{t("reasonMatch")}</li>
        </ul>
        <div className="flex flex-wrap gap-2 border-t border-line-soft pt-3.5">
          <Link href="/" className={buttonVariants()}>
            {me ? t("home") : t("signIn")}
          </Link>
          {me && (
            <>
              <Link href="/matches" className={buttonVariants({ variant: "outline" })}>
                {t("matches")}
              </Link>
              <Link href="/sessions" className={buttonVariants({ variant: "outline" })}>
                {t("sessions")}
              </Link>
            </>
          )}
        </div>
      </Panel>
      {discord && (
        <p className="text-sm text-muted-foreground">
          {t.rich("report", {
            link: (chunks) => (
              <a
                href={discord}
                target="_blank"
                rel="noopener noreferrer"
                className="text-link underline underline-offset-3"
              >
                {chunks}
              </a>
            ),
          })}
        </p>
      )}
    </section>
  );
}
