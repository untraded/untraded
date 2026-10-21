// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { cn } from "@/lib/cn";

/** The admin's title and its two pages, the current one marked. */
export async function AdminHeader({ current }: { current: "players" | "health" }) {
  const t = await getTranslations("admin");
  const tabs = [
    { key: "players", href: "/admin", label: t("players") },
    { key: "health", href: "/admin/health", label: t("health") },
  ] as const;
  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold sm:text-[1.75rem]">{t("title")}</h1>
      <nav aria-label={t("title")} className="flex gap-1 border-b border-border">
        {tabs.map((tab) => (
          <Link
            key={tab.key}
            href={tab.href}
            aria-current={tab.key === current ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground hover:text-foreground",
              "aria-[current=page]:border-highlight aria-[current=page]:font-semibold aria-[current=page]:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
