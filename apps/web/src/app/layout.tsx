// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { getLocale } from "next-intl/server";
import type { ReactNode } from "react";
import { Header } from "@/components/header";
import { getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { plexMono, plexSans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Untraded", template: "%s · Untraded" },
  description: "Open, transparent Counter-Strike 2 match analysis.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const [locale, me] = await Promise.all([getLocale(), getMe()]);
  return (
    <html lang={locale} className={cn(plexSans.variable, plexMono.variable)}>
      <body>
        <Header me={me} />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
