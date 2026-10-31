// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { TeamShell } from "@/components/team/team-shell";
import { getMe } from "@/lib/api";
import { TeamPreviewProvider } from "@/lib/team-preview/store";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("team"))("title") };
}

/**
 * The team mode preview: a mock-up with an invented team, for admins only, no API. Its pages are
 * client side (what a visitor adds stays in their browser), so they get the `team` messages.
 */
export default async function TeamLayout({ children }: { children: ReactNode }) {
  const me = await getMe();
  if (!me?.admin) notFound();
  const messages = await getMessages();
  return (
    <NextIntlClientProvider messages={{ team: messages.team }}>
      <TeamPreviewProvider>
        <TeamShell>{children}</TeamShell>
      </TeamPreviewProvider>
    </NextIntlClientProvider>
  );
}
