// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import type { Me } from "@/lib/api";
import { AccountMenu } from "./account-menu";
import { MoreSheet } from "./more-sheet";
import { NavLink } from "./nav-link";
import { SidebarToggle } from "./sidebar-toggle";

/**
 * The frame of every signed-in page. From 768 px: a sidebar (240 px, foldable to its icons, always
 * folded below 1024 px). Below: a slim top bar and four tabs at the bottom of the screen.
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
      className="group/shell min-h-dvh md:grid md:grid-cols-[60px_minmax(0,1fr)] lg:grid-cols-[240px_minmax(0,1fr)] lg:data-[collapsed=true]:grid-cols-[60px_minmax(0,1fr)]"
    >
      <aside className="sticky top-0 hidden h-dvh flex-col gap-0.5 border-r border-border bg-card px-2.5 py-3 md:flex">
        <div className="flex items-center justify-center gap-2 px-1 pb-3 lg:justify-between lg:group-data-[collapsed=true]/shell:flex-col lg:group-data-[collapsed=true]/shell:justify-center">
          <Link href="/" aria-label="Untraded" className="px-1 text-base font-bold">
            <span
              aria-hidden="true"
              className="hidden lg:inline lg:group-data-[collapsed=true]/shell:hidden"
            >
              Untraded
            </span>
            <span
              aria-hidden="true"
              className="lg:hidden lg:group-data-[collapsed=true]/shell:inline"
            >
              U
            </span>
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
              workspace: t("workspace", { name: me.display_name }),
              personal: t("personal"),
              signOut: t("signOut"),
            }}
          />
        </div>
        <nav aria-label={t("main")} className="flex flex-1 flex-col gap-0.5">
          <NavLink section="home" label={t("home")} place="sidebar" />
          <NavLink section="sessions" label={t("sessions")} place="sidebar" />
          <NavLink section="matches" label={t("matches")} place="sidebar" />
          <div className="mt-auto">
            <NavLink section="settings" label={t("settings")} place="sidebar" />
          </div>
        </nav>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-10 flex h-13 items-center border-b border-border bg-card px-4 md:hidden">
          <Link href="/" className="font-bold">
            Untraded
          </Link>
        </header>
        <main className="mx-auto max-w-6xl px-4 pt-6 pb-24 md:px-8 md:pt-8 md:pb-12">
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
        <MoreSheet labels={{ more: t("more"), settings: t("settings"), signOut: t("signOut") }} />
      </nav>
    </div>
  );
}
