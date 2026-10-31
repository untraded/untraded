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
 * The frame of every signed-in page. From 768 px: a sidebar (240 px, foldable to its icons). Below:
 * a slim top bar and four tabs at the bottom of the screen. The sections a player uses come first;
 * how the numbers are calculated, the settings and the admin sit at the bottom.
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
      className="group/shell min-h-dvh md:grid md:grid-cols-[240px_minmax(0,1fr)] md:data-[collapsed=true]:grid-cols-[60px_minmax(0,1fr)]"
    >
      <aside className="sticky top-0 hidden h-dvh flex-col gap-0.5 border-r border-border bg-card px-2.5 py-3 md:flex">
        <div className="flex items-center justify-center gap-2 px-1 pb-3 md:justify-between md:group-data-[collapsed=true]/shell:flex-col md:group-data-[collapsed=true]/shell:justify-center">
          <Link href="/" aria-label="Untraded" className="flex h-8 items-center rounded-md px-1">
            {/* The logo when the sidebar is wide; folded, the compact sign alone, in its version
                drawn for small sizes. */}
            <LogoHorizontal className="hidden h-5 w-auto md:block md:group-data-[collapsed=true]/shell:hidden" />
            <LogoSymbol16 className="size-4 md:hidden md:group-data-[collapsed=true]/shell:block" />
          </Link>
          <SidebarToggle
            collapsed={collapsed}
            labels={{ collapse: t("collapse"), expand: t("expand") }}
          />
        </div>
        <div className="mb-3">
          <AccountMenu
            name={me.display_name}
            labels={{
              account: t("account", { name: me.display_name }),
              settings: t("settings"),
              signOut: t("signOut"),
            }}
          />
        </div>
        <nav aria-label={t("main")} className="flex flex-1 flex-col gap-0.5">
          <NavLink section="home" label={t("home")} place="sidebar" />
          <NavLink section="sessions" label={t("sessions")} place="sidebar" />
          <NavLink section="matches" label={t("matches")} place="sidebar" />
          <NavLink section="progress" label={t("progress")} place="sidebar" />
          <NavLink section="upload" label={t("upload")} place="sidebar" />
          {me.admin && (
            <NavLink section="team" label={t("team")} badge={t("preview")} place="sidebar" />
          )}
          <div className="mt-auto flex flex-col gap-0.5">
            <NavLink section="formulas" label={t("formulas")} place="sidebar" />
            <NavLink section="settings" label={t("settings")} place="sidebar" />
            {me.admin && <NavLink section="admin" label={t("admin")} place="sidebar" />}
          </div>
        </nav>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-10 flex h-13 items-center border-b border-border bg-card px-4 md:hidden">
          <Link href="/" aria-label="Untraded" className="flex h-8 items-center">
            <LogoHorizontal className="h-5 w-auto" />
          </Link>
        </header>
        <main className="mx-auto max-w-6xl px-4 pt-6 pb-24 md:px-8 md:pt-8 md:pb-12">
          {me.demo && <DemoBanner />}
          {children}
        </main>
      </div>

      <nav
        aria-label={t("main")}
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-4 border-t border-border bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
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
