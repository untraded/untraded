// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { LogoHorizontal, LogoSymbol16 } from "@/components/brand/logo";
import { DemoBanner } from "@/components/demo-banner";
import type { Me } from "@/lib/api";
import { AccountMenu } from "./account-menu";
import { MoreSheet } from "./more-sheet";
import { NavLink } from "./nav-link";
import { SidebarToggle } from "./sidebar-toggle";

/**
 * The frame of every signed-in page, in the "Instrument" direction. From 768 px: a dark rail of
 * icons (58 px), each label a tooltip; the player can show the labels beside the icons (220 px),
 * a choice kept in a cookie. Below 768 px: a slim top bar and four tabs at the bottom of the
 * screen. Rail, top bar and tabs are the chrome: dark in both themes. The sections a player uses
 * come first; how the numbers are calculated, the settings, the admin and the account sit at the
 * bottom.
 */
export async function AppShell({
  me,
  collapsed,
  children,
}: {
  me: Me;
  collapsed: boolean;
  children: ReactNode;
}) {
  const t = await getTranslations("nav");
  return (
    <div
      data-collapsed={collapsed}
      className="group/shell min-h-dvh md:grid md:grid-cols-[58px_minmax(0,1fr)] md:data-[collapsed=false]:grid-cols-[220px_minmax(0,1fr)]"
    >
      {/* The first stop of the keyboard: past the rail, straight to the page. */}
      <a
        href="#content"
        className="sr-only z-30 rounded-md bg-card text-sm font-semibold focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:px-3 focus:py-2"
      >
        {t("skip")}
      </a>
      <aside
        data-chrome
        className="sticky top-0 z-20 hidden h-dvh flex-col gap-0.5 px-2 py-3 md:flex"
      >
        <div className="flex flex-col items-center gap-2 pb-3 md:group-data-[collapsed=false]/shell:flex-row md:group-data-[collapsed=false]/shell:justify-between md:group-data-[collapsed=false]/shell:pl-1.5">
          <Link href="/" aria-label="Untraded" className="flex h-8 items-center rounded-md px-1">
            {/* Folded, the compact sign alone, in its version drawn for small sizes; unfolded, the
                logo. */}
            <LogoSymbol16 className="size-4 md:group-data-[collapsed=false]/shell:hidden" />
            <LogoHorizontal className="hidden h-5 w-auto md:group-data-[collapsed=false]/shell:block" />
          </Link>
          <SidebarToggle
            collapsed={collapsed}
            labels={{ collapse: t("collapse"), expand: t("expand") }}
          />
        </div>
        <nav aria-label={t("main")} className="flex flex-1 flex-col gap-0.5">
          <NavLink section="home" label={t("home")} place="rail" />
          <NavLink section="sessions" label={t("sessions")} place="rail" />
          <NavLink section="matches" label={t("matches")} place="rail" />
          <NavLink section="progress" label={t("progress")} place="rail" />
          <NavLink section="upload" label={t("upload")} place="rail" />
          {me.admin && (
            <NavLink section="team" label={t("team")} badge={t("preview")} place="rail" />
          )}
          <div className="mt-auto flex flex-col gap-0.5">
            <NavLink section="formulas" label={t("formulas")} place="rail" />
            <NavLink section="settings" label={t("settings")} place="rail" />
            {me.admin && <NavLink section="admin" label={t("admin")} place="rail" />}
          </div>
        </nav>
        <div className="mt-2 border-t border-chrome-line pt-2">
          <AccountMenu
            name={me.display_name}
            labels={{
              account: t("account", { name: me.display_name }),
              settings: t("settings"),
              signOut: t("signOut"),
            }}
          />
        </div>
      </aside>

      {/* A size container, so that a context bar can run edge to edge of it (`cqw`). It is also
          the containing block of any `position: fixed` inside it: put such elements outside. */}
      <div className="@container min-w-0">
        <header
          data-chrome
          className="sticky top-0 z-10 flex h-13 items-center border-b border-chrome-line px-4 md:hidden"
        >
          <Link href="/" aria-label="Untraded" className="flex h-8 items-center">
            <LogoHorizontal className="h-5 w-auto" />
          </Link>
        </header>
        <main
          id="content"
          tabIndex={-1}
          className="mx-auto max-w-6xl px-4 pt-6 pb-24 md:px-8 md:pt-8 md:pb-12"
        >
          {me.demo && <DemoBanner />}
          {children}
        </main>
      </div>

      <nav
        data-chrome
        aria-label={t("main")}
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-4 border-t border-chrome-line pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <NavLink section="home" label={t("home")} place="tab" />
        <NavLink section="sessions" label={t("sessions")} place="tab" />
        <NavLink section="matches" label={t("matches")} place="tab" />
        <MoreSheet
          labels={{
            more: t("more"),
            settings: t("settings"),
            progress: t("progress"),
            upload: t("upload"),
            formulas: t("formulas"),
            admin: me.admin ? t("admin") : null,
            team: me.admin ? t("team") : null,
            preview: t("preview"),
            signOut: t("signOut"),
          }}
        />
      </nav>
    </div>
  );
}
