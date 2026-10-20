// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { Report } from "@/components/report";
import { getSession, getSessions } from "@/lib/api";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("nav"))("report") };
}

/** Where a signed-in player lands: the report of their latest session. */
export default async function LatestReport() {
  const list = await getSessions(0);
  if (!list) redirect("/");
  const latest = list.items[0];
  if (!latest) {
    const t = await getTranslations();
    return (
      <section>
        <h1 className="text-2xl font-semibold">{t("nav.report")}</h1>
        <p className="mt-2 max-w-prose text-muted-foreground">{t("sessions.empty")}</p>
      </section>
    );
  }
  const report = await getSession(latest.id);
  if (!report) redirect("/");
  return <Report report={report} back={false} />;
}
