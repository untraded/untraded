// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Eye, Info, Lock, RotateCcw } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { PreviewBadge } from "@/components/shell/preview-badge";
import { ContextBar } from "@/components/ui/context-bar";
import { TEAM } from "@/lib/team-preview/data";
import { useTeamPreview } from "@/lib/team-preview/store";
import { PAGES, type Page, ROLES } from "@/lib/team-preview/types";

const HREF: Record<Page, string> = {
  roster: "/team",
  lineups: "/team/lineups",
  execs: "/team/execs",
  strats: "/team/strats",
  stats: "/team/stats",
};

/** The page a path belongs to. */
export function pageOf(pathname: string): Page {
  return PAGES.find((p) => p !== "roster" && pathname.startsWith(HREF[p])) ?? "roster";
}

/**
 * The frame of the preview. Its context bar holds the team's name (the page's title) with the
 * "Preview" badge, its pages (the current one a filled tab with a rule under it; one the role may
 * not open carries a lock), and at the right "view as", the role the pages are seen with so that
 * permissions show their effect, and the reset. Under it, one line says what the preview is.
 */
export function TeamShell({ children }: { children: ReactNode }) {
  const t = useTranslations("team");
  const { viewAs, setViewAs, matrix, reset, ready } = useTeamPreview();
  const page = pageOf(usePathname());
  const open = matrix[page][viewAs] !== "none";
  return (
    <>
      <ContextBar label={t("context.label")}>
        <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 xl:shrink-0">
          <h1 className="text-lg leading-tight font-semibold">
            {TEAM.name}{" "}
            <span className="text-sm font-medium text-muted-foreground">[{TEAM.tag}]</span>
          </h1>
          <PreviewBadge label={t("badge")} className="self-center" />
        </div>
        <nav
          aria-label={t("pages")}
          className="-mx-1 max-w-full overflow-x-auto px-1 max-xl:order-last max-xl:basis-full xl:min-w-0"
        >
          <ul className="flex min-w-max gap-1">
            {PAGES.map((p) => {
              const closed = matrix[p][viewAs] === "none";
              return (
                <li key={p}>
                  <Link
                    href={HREF[p]}
                    aria-current={p === page ? "page" : undefined}
                    className="inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-highlight-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground aria-[current=page]:shadow-[inset_0_-2px_0_var(--highlight)]"
                  >
                    {t(`pagesNames.${p}`)}
                    {closed && (
                      <>
                        <Lock aria-hidden="true" className="size-3" />
                        <span className="sr-only">
                          {" "}
                          ({t("closedFor", { role: t(`roles.${viewAs}`) })})
                        </span>
                      </>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 lg:ml-auto xl:shrink-0">
          <label className="flex items-center gap-2 text-[0.8125rem]">
            <Eye aria-hidden="true" className="size-4 text-muted-foreground" />
            <span className="text-muted-foreground max-sm:sr-only">{t("viewAs")}</span>
            <select
              value={viewAs}
              onChange={(event) => setViewAs(event.target.value as (typeof ROLES)[number])}
              className="h-8 rounded-md border border-input bg-card px-2 text-sm"
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {t(`roles.${role}`)}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={reset}
            className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md px-2 text-[0.8125rem] text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            {t("reset")}
          </button>
        </div>
      </ContextBar>
      <div className="flex flex-col gap-4">
        <p role="note" className="flex items-start gap-2 text-[0.8125rem] text-muted-foreground">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            <span className="font-semibold text-foreground">{t("preview")}</span> {t("previewHint")}
          </span>
        </p>
        {/* Until the browser's copy is read, nothing: the pages would show as the owner, and a
          role that may not see staff items would glimpse them. */}
        {!ready ? (
          <p
            aria-busy="true"
            className="h-40 animate-pulse rounded-lg border border-border bg-card"
          >
            <span className="sr-only">{t("loading")}</span>
          </p>
        ) : open ? (
          children
        ) : (
          <p className="flex items-start gap-2 rounded-lg border border-border bg-card px-3.5 py-3 text-sm text-muted-foreground">
            <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {t("noAccess", { role: t(`roles.${viewAs}`) })}
          </p>
        )}
      </div>
    </>
  );
}
