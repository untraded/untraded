// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import { getLocale, getTranslations } from "next-intl/server";
import { setLocale, signOut } from "@/app/actions";
import { LOCALES } from "@/i18n/locale";
import type { Me } from "@/lib/api";
import { cn } from "@/lib/cn";

export async function Header({ me }: { me: Me | null }) {
  const t = await getTranslations("nav");
  const locale = await getLocale();
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="font-semibold tracking-tight">
          Untraded
        </Link>
        {me && (
          <nav className="flex gap-4 text-sm text-foreground">
            <Link href="/sessions" className="hover:text-foreground">
              {t("sessions")}
            </Link>
            <Link href="/matches" className="hover:text-foreground">
              {t("matches")}
            </Link>
          </nav>
        )}
        <div className="ml-auto flex items-center gap-4 text-sm">
          <form action={setLocale} className="flex gap-1" aria-label={t("language")}>
            {LOCALES.map((code) => (
              <button
                key={code}
                type="submit"
                name="locale"
                value={code}
                className={cn(
                  "rounded px-1.5 py-0.5 uppercase",
                  code === locale
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {code}
              </button>
            ))}
          </form>
          {me && (
            <>
              <span className="text-muted-foreground">{me.display_name}</span>
              <form action={signOut}>
                <button type="submit" className="text-muted-foreground hover:text-foreground">
                  {t("signOut")}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
