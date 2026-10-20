// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

import { LogIn } from "lucide-react";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { buttonVariants } from "@/components/ui/button";
import { getMe, PUBLIC_API_PATH } from "@/lib/api";
import { cn } from "@/lib/cn";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ signin?: string }>;
}) {
  if (await getMe()) redirect("/sessions");
  const t = await getTranslations("home");
  const { signin } = await searchParams;
  const problem =
    signin === "not_invited" ? t("notInvited") : signin === "failed" ? t("failed") : null;
  return (
    <section className="mx-auto max-w-2xl py-16 text-center">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-4 text-muted-foreground">{t("lead")}</p>
      {problem && (
        <p role="alert" className="mt-8 rounded border border-loss/40 bg-loss/10 px-4 py-3 text-sm">
          {problem}
        </p>
      )}
      <a href={`${PUBLIC_API_PATH}/auth/steam`} className={cn(buttonVariants(), "mt-10")}>
        <LogIn data-icon="inline-start" aria-hidden="true" />
        {t("signIn")}
      </a>
      <p className="mt-3 text-xs text-muted-foreground">{t("beta")}</p>
    </section>
  );
}
