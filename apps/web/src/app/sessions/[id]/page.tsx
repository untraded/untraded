// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { Report } from "@/components/report";
import { getMe, getSession } from "@/lib/api";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("sessions"))("title") };
}

export default async function SessionPage({ params }: Params) {
  const [report, me] = await Promise.all([getSession((await params).id), getMe()]);
  if (!report) redirect("/");
  return <Report report={report} back readOnly={Boolean(me?.demo)} />;
}
