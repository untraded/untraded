// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import { getLocale, getTimeZone } from "next-intl/server";
import type { ReactNode } from "react";
import { PwaSetup } from "@/components/pwa/pwa-setup";
import { AppShell } from "@/components/shell/app-shell";
import { TimeZoneSync } from "@/components/time-zone-sync";
import { pickTheme, SIDEBAR_COOKIE, THEME_COOKIE } from "@/i18n/locale";
import { getMe } from "@/lib/api";
import { cn } from "@/lib/cn";
import { themeColor } from "@/lib/theme-color";
import { plexMono, plexSans } from "./fonts";
import "./globals.css";

/** The site's public address (`UNTRADED_SITE_URL`), so the share image and the icons are linked
 * from it rather than from the container's own `localhost`. */
function siteUrl(): URL | undefined {
  try {
    return process.env.UNTRADED_SITE_URL ? new URL(process.env.UNTRADED_SITE_URL) : undefined;
  } catch {
    return undefined;
  }
}

export function generateMetadata(): Metadata {
  return {
    metadataBase: siteUrl(),
    title: { default: "Untraded", template: "%s · Untraded" },
    description: "Open, transparent Counter-Strike 2 match analysis.",
    // Linked by hand: a route of ours (`app/manifest.webmanifest/route.ts`), not `app/manifest.ts`.
    manifest: "/manifest.webmanifest",
    // Installed from Safari's Share menu: the app's name, and a dark status bar over the chrome.
    appleWebApp: { capable: true, title: "Untraded", statusBarStyle: "black" },
  };
}

/** The browser's bar takes the chrome's colour, in the player's theme (`lib/theme-color.ts`). */
export async function generateViewport(): Promise<Viewport> {
  const store = await cookies();
  return { themeColor: themeColor(pickTheme(store.get(THEME_COOKIE)?.value)) };
}

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
        <PwaSetup />
        {me ? (
          <AppShell me={me} collapsed={store.get(SIDEBAR_COOKIE)?.value !== "expanded"}>
            {children}
          </AppShell>
        ) : (
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        )}
      </body>
    </html>
  );
}
