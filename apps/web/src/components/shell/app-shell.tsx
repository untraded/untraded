// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { LogoHorizontal, LogoSymbol16 } from "@/components/brand/logo";
import { DemoBanner } from "@/components/demo-banner";
import { roleLabel } from "@/components/teams/role-label";
import type { Me, WorkspaceRef } from "@/lib/api";
import { cn } from "@/lib/cn";
import { initials, PERSONAL_SPACE } from "@/lib/space";
import { isDefaultRole, teamHref, teamsOf } from "@/lib/teams";
import { AccountMenu } from "./account-menu";
import { MoreSheet } from "./more-sheet";
import { RAIL_MOTION } from "./nav";
import { NavLink } from "./nav-link";
import { SidebarToggle } from "./sidebar-toggle";
import { SpaceMemory, SpaceSwitch } from "./space";
import { SpaceMenu } from "./space-menu";
import { SpaceSheet } from "./space-sheet";
import type { SpaceLink } from "./space-trigger";

/**
 * The frame of every signed-in page, in the "Instrument" direction. From 768 px: a dark rail of
 * icons (58 px), each label a tooltip; on a touch screen (no hover), a short label under each icon
 * instead (72 px). The player can show the labels beside the icons (220 px), a choice kept in a
 * cookie. Below 768 px: a slim top bar and four tabs at the bottom of the
 * screen. Rail, top bar and tabs are the chrome: dark in both themes. The sections a player uses
 * come first; how the numbers are calculated, the settings, the admin and the account sit at the
 * bottom.
 *
 * A player in a team has workspaces: their own and each team's. The address says which is open
 * (`/teams/<slug>/…` is that team's), a switch at the head of the rail (in the phone's top bar)
 * changes it, and the whole navigation follows: a team's space links only the team's pages.
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
  const [t, teamsT, locale] = await Promise.all([
    getTranslations("nav"),
    getTranslations("teams"),
    getLocale(),
  ]);
  const teams = teamsOf(me);
  const slugs = teams.map((w) => w.slug);
  const spaces = teams.length > 0 ? spacesOf(me, teams, teamsT, locale) : [];
  const switchProps = { spaces, title: teamsT("switcher.title") };
  const moreLabels = {
    more: t("more"),
    settings: t("settings"),
    progress: t("progress"),
    upload: t("upload"),
    formulas: t("formulas"),
    admin: me.admin ? t("admin") : null,
    team: me.admin ? t("team") : null,
    preview: t("preview"),
    signOut: t("signOut"),
  };
  return (
    <div
      data-collapsed={collapsed}
      className={cn(
        "group/shell min-h-dvh transition-[grid-template-columns] md:grid md:grid-cols-[58px_minmax(0,1fr)] md:data-[collapsed=false]:grid-cols-[220px_minmax(0,1fr)] touch-folded:grid-cols-[72px_minmax(0,1fr)]",
        RAIL_MOTION,
      )}
    >
      {spaces.length > 0 && <SpaceMemory slugs={slugs} />}
      {/* The first stop of the keyboard: past the rail, straight to the page. */}
      <a
        href="#content"
        className="sr-only z-30 rounded-md bg-card text-sm font-semibold focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:px-3 focus:py-2"
      >
        {t("skip")}
      </a>
      <aside
        data-chrome
        className="sticky top-0 z-20 hidden h-dvh flex-col gap-0.5 px-2 py-3 md:flex touch-rail:overflow-y-auto touch-rail:overscroll-contain"
      >
        {/* The head: folded, the sign (or the workspace switch) over the toggle; unfolded, the
            logo (or the switch) and the toggle on one line. Its height moves with the rail's
            width, so the links below slide, not jump. */}
        <div
          className={cn(
            "relative mb-3 h-[68px] shrink-0 transition-[height] touch-rail:h-20 md:group-data-[collapsed=false]/shell:h-8",
            spaces.length > 0 && "touch-rail:h-[96px] md:group-data-[collapsed=false]/shell:h-11",
            RAIL_MOTION,
          )}
        >
          {spaces.length > 0 ? (
            <SpaceMenu {...switchProps} />
          ) : (
            <Link
              href="/"
              aria-label="Untraded"
              className="relative block h-8 overflow-hidden rounded-md"
            >
              {/* Folded, the compact sign alone, in its version drawn for small sizes; unfolded,
                  the logo. One fades into the other, the logo cut by the rail's edge as it
                  moves. */}
              <LogoSymbol16
                className={cn(
                  "absolute top-2 left-[13px] size-4 transition-opacity touch-rail:left-5 md:group-data-[collapsed=false]/shell:opacity-0",
                  RAIL_MOTION,
                )}
              />
              <LogoHorizontal
                className={cn(
                  "absolute top-1.5 left-[11px] h-5 w-auto max-w-none opacity-0 transition-opacity md:group-data-[collapsed=false]/shell:opacity-100",
                  RAIL_MOTION,
                )}
              />
            </Link>
          )}
          <SidebarToggle
            collapsed={collapsed}
            tall={spaces.length > 0}
            labels={{ collapse: t("collapse"), expand: t("expand") }}
          />
        </div>
        <nav aria-label={t("main")} className="flex flex-1 flex-col gap-0.5">
          <SpaceSwitch
            slugs={slugs}
            personal={
              <>
                <NavLink section="home" label={t("home")} short={t("short.home")} place="rail" />
                <NavLink
                  section="sessions"
                  label={t("sessions")}
                  short={t("short.sessions")}
                  place="rail"
                />
                <NavLink
                  section="matches"
                  label={t("matches")}
                  short={t("short.matches")}
                  place="rail"
                />
                <NavLink
                  section="progress"
                  label={t("progress")}
                  short={t("short.progress")}
                  place="rail"
                />
                <NavLink
                  section="upload"
                  label={t("upload")}
                  short={t("short.upload")}
                  place="rail"
                />
                {me.admin && (
                  <NavLink
                    section="team"
                    label={t("team")}
                    short={t("short.team")}
                    badge={t("preview")}
                    place="rail"
                  />
                )}
                <div className="mt-auto flex flex-col gap-0.5">
                  <NavLink
                    section="formulas"
                    label={t("formulas")}
                    short={t("short.formulas")}
                    place="rail"
                  />
                  <NavLink
                    section="settings"
                    label={t("settings")}
                    short={t("short.settings")}
                    place="rail"
                  />
                  {me.admin && (
                    <NavLink
                      section="admin"
                      label={t("admin")}
                      short={t("short.admin")}
                      place="rail"
                    />
                  )}
                </div>
              </>
            }
            // A team's space links only the pages that exist: its home and its members. Its
            // matches, stats, review and the rest join this list as they are built.
            teams={Object.fromEntries(
              teams.map((w) => [
                w.slug,
                <>
                  <NavLink
                    section="home"
                    href={teamHref(w.slug)}
                    exact
                    label={t("teamHome")}
                    short={t("short.teamHome")}
                    place="rail"
                  />
                  <div className="mt-auto flex flex-col gap-0.5">
                    <NavLink
                      section="teams"
                      href={teamHref(w.slug, "members")}
                      label={t("teamMembers")}
                      short={t("short.teamMembers")}
                      place="rail"
                    />
                  </div>
                </>,
              ]),
            )}
          />
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
          className="sticky top-0 z-10 flex h-13 items-center border-b border-chrome-line px-3 md:hidden"
        >
          {spaces.length > 0 ? (
            <SpaceSheet {...switchProps} />
          ) : (
            <Link href="/" aria-label="Untraded" className="flex h-8 items-center px-1">
              <LogoHorizontal className="h-5 w-auto" />
            </Link>
          )}
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
        className="fixed inset-x-0 bottom-0 z-10 border-t border-chrome-line pb-[env(safe-area-inset-bottom)] md:hidden"
      >
        <SpaceSwitch
          slugs={slugs}
          personal={
            <div className="grid grid-cols-4">
              <NavLink section="home" label={t("home")} place="tab" />
              <NavLink section="sessions" label={t("sessions")} place="tab" />
              <NavLink section="matches" label={t("matches")} place="tab" />
              <MoreSheet labels={moreLabels} />
            </div>
          }
          teams={Object.fromEntries(
            teams.map((w) => [
              w.slug,
              <div key={w.slug} className="grid grid-cols-3">
                <NavLink
                  section="home"
                  href={teamHref(w.slug)}
                  exact
                  label={t("teamHome")}
                  place="tab"
                />
                <NavLink
                  section="teams"
                  href={teamHref(w.slug, "members")}
                  label={t("teamMembers")}
                  place="tab"
                />
                <MoreSheet labels={{ ...moreLabels, progress: null, upload: null, team: null }} />
              </div>,
            ]),
          )}
        />
      </nav>
    </div>
  );
}

/** The player's own space, then each team's, as the switch lists them. */
function spacesOf(
  me: Me,
  teams: WorkspaceRef[],
  t: (key: string, values?: Record<string, string>) => string,
  locale: string,
): SpaceLink[] {
  const mine = t("switcher.personal");
  return [
    {
      key: PERSONAL_SPACE,
      name: me.display_name,
      menuName: mine,
      badge: Array.from(me.display_name.trim())[0] ?? "?",
      team: false,
      line: mine,
      role: null,
      // The choice of the player's own space: the home page then stays there.
      href: "/?space=personal",
      // Named by what it shows (the player's name), so that voice control finds it.
      label: t("switcher.switch", { name: me.display_name }),
    },
    ...teams.map((w) => {
      const role = roleLabel(t, w.role);
      return {
        key: w.slug,
        name: w.name,
        menuName: w.name,
        badge: initials(w.name),
        team: true,
        // "Team · owner": the default roles in lower case after the dot, a team's own as named.
        line: t("switcher.teamLine", {
          role: isDefaultRole(w.role) ? role.toLocaleLowerCase(locale) : role,
        }),
        role,
        href: teamHref(w.slug),
        label: t("switcher.switch", { name: w.name }),
      };
    }),
  ];
}
