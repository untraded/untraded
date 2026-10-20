// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { getMe, publicApiUrl } from "@/lib/api";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ signin?: string }>;
}) {
  if (await getMe()) redirect("/matches");
  const t = await getTranslations("home");
  const { signin } = await searchParams;
  const problem =
    signin === "not_invited" ? t("notInvited") : signin === "failed" ? t("failed") : null;
  return (
    <section className="mx-auto max-w-2xl py-16 text-center">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t("title")}</h1>
      <p className="mt-4 text-zinc-400">{t("lead")}</p>
      {problem && (
        <p role="alert" className="mt-8 rounded border border-loss/40 bg-loss/10 px-4 py-3 text-sm">
          {problem}
        </p>
      )}
      <a
        href={`${publicApiUrl()}/auth/steam`}
        className="mt-10 inline-block rounded bg-zinc-100 px-5 py-2.5 font-medium text-zinc-950 hover:bg-white"
      >
        {t("signIn")}
      </a>
      <p className="mt-3 text-xs text-zinc-500">{t("beta")}</p>
    </section>
  );
}
