// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { ContextBar } from "@/components/ui/context-bar";

/**
 * The admin's context bar, which also holds its title: "Admin", its two pages (the current one
 * marked by a filled tab with a rule under it and `aria-current`, not the colour alone), and at
 * the right what the page sums up (counts on Players, the worst state on Health).
 */
export async function AdminHeader({
  current,
  children,
}: {
  current: "players" | "health";
  /** The page's summary, at the right of the bar. */
  children?: ReactNode;
}) {
  const t = await getTranslations("admin");
  const tabs = [
    { key: "players", href: "/admin", label: t("players") },
    { key: "health", href: "/admin/health", label: t("health") },
  ] as const;
  return (
    <ContextBar label={t("context.label")}>
      <h1 className="text-lg leading-tight font-semibold xl:shrink-0">{t("title")}</h1>
      <nav aria-label={t("title")} className="xl:shrink-0">
        <ul className="flex gap-1">
          {tabs.map((tab) => (
            <li key={tab.key}>
              <Link
                href={tab.href}
                aria-current={tab.key === current ? "page" : undefined}
                className="inline-flex h-7 items-center rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-highlight-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground aria-[current=page]:shadow-[inset_0_-2px_0_var(--highlight)]"
              >
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {children && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[0.8125rem] lg:ml-auto xl:shrink-0 xl:flex-nowrap">
          {children}
        </div>
      )}
    </ContextBar>
  );
}
