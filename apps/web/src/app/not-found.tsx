// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { buttonVariants } from "@/components/ui/button";
import { getMe } from "@/lib/api";
import { discordUrl } from "@/lib/site";

export default async function NotFound() {
  const [me, t] = await Promise.all([getMe(), getTranslations("notFound")]);
  const discord = discordUrl();
  return (
    <section className="mx-auto flex max-w-xl flex-col gap-6 py-12 sm:py-16">
      <div className="flex flex-col gap-3">
        <p className="font-mono text-sm text-muted-foreground tabular-nums">404</p>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="flex flex-col gap-2 text-sm">
        <p className="font-medium">{t("why")}</p>
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-muted-foreground">
          <li>{t("reasonLink")}</li>
          <li>{t("reasonMatch")}</li>
        </ul>
      </div>
      <div className="flex flex-wrap gap-2">
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
      {discord && (
        <p className="text-sm text-muted-foreground">
          {t.rich("report", {
            link: (chunks) => (
              <a href={discord} className={buttonVariants({ variant: "link" })}>
                {chunks}
              </a>
            ),
          })}
        </p>
      )}
    </section>
  );
}
