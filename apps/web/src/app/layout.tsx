// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { cookies } from "next/headers";
import { getLocale, getTimeZone } from "next-intl/server";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { TimeZoneSync } from "@/components/time-zone-sync";
import { pickTheme, SIDEBAR_COOKIE, THEME_COOKIE } from "@/i18n/locale";
import { getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { plexMono, plexSans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Untraded", template: "%s · Untraded" },
  description: "Open, transparent Counter-Strike 2 match analysis.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const [locale, me, store, timeZone] = await Promise.all([
    getLocale(),
    getMe(),
    cookies(),
    getTimeZone(),
  ]);
  const theme = pickTheme(store.get(THEME_COOKIE)?.value);
  return (
    <html
      lang={locale}
      data-theme={theme === "system" ? undefined : theme}
      className={cn(plexSans.variable, plexMono.variable)}
    >
      <body>
        <TimeZoneSync current={timeZone} />
        {me ? (
          <AppShell me={me} collapsed={store.get(SIDEBAR_COOKIE)?.value === "collapsed"}>
            {children}
          </AppShell>
        ) : (
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        )}
      </body>
    </html>
  );
}
