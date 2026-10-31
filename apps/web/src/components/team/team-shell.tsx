// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Eye } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
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
 * The frame of the preview: the banner that says it is one, the team's name, its pages, and
 * "view as": the role the pages are seen with, so permissions show their effect.
 */
export function TeamShell({ children }: { children: ReactNode }) {
  const t = useTranslations("team");
  const { viewAs, setViewAs, matrix, reset } = useTeamPreview();
  const page = pageOf(usePathname());
  const open = matrix[page][viewAs] !== "none";
  return (
    <section className="flex flex-col gap-5">
      <p
        role="note"
        className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-dashed border-border bg-card px-3.5 py-2.5 text-[0.8125rem]"
      >
        <span className="font-semibold">{t("preview")}</span>
        <span className="text-muted-foreground">{t("previewHint")}</span>
        <button
          type="button"
          onClick={reset}
          className="ml-auto cursor-pointer text-link underline underline-offset-3"
        >
          {t("reset")}
        </button>
      </p>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[0.8125rem] text-muted-foreground">{t("title")}</p>
          <h1 className="text-2xl font-semibold md:text-[1.75rem]">
            {TEAM.name}{" "}
            <span className="text-base font-medium text-muted-foreground">[{TEAM.tag}]</span>
          </h1>
        </div>
        <label className="flex items-center gap-2 text-[0.8125rem]">
          <Eye aria-hidden="true" className="size-4 text-muted-foreground" />
          <span className="text-muted-foreground">{t("viewAs")}</span>
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
      </header>
      <nav aria-label={t("pages")} className="-mx-1 overflow-x-auto">
        <ul className="flex min-w-max gap-1 border-b border-border px-1">
          {PAGES.map((p) => (
            <li key={p}>
              <Link
                href={HREF[p]}
                aria-current={p === page ? "page" : undefined}
                className={cn(
                  "-mb-px flex h-9 items-center border-b-2 border-transparent px-3 text-sm text-muted-foreground hover:text-foreground",
                  p === page && "border-highlight font-semibold text-foreground",
                  matrix[p][viewAs] === "none" && "opacity-50",
                )}
              >
                {t(`pagesNames.${p}`)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {open ? (
        children
      ) : (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {t("noAccess", { role: t(`roles.${viewAs}`) })}
        </p>
      )}
    </section>
  );
}
