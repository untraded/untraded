// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import { PUBLIC_API_PATH } from "@/lib/api-path";

/** On every page of the public demo: what it is, and how to get a real account (signing in with
 * Steam: a player not yet invited can ask for an invitation there). */
export async function DemoBanner() {
  const t = await getTranslations("demo");
  return (
    <p
      role="note"
      className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-dashed border-border bg-card px-3.5 py-2.5 text-[0.8125rem]"
    >
      <span className="font-semibold">{t("banner")}</span>
      <a
        href={`${PUBLIC_API_PATH}/auth/steam`}
        className="ml-auto text-link underline underline-offset-3"
      >
        {t("invite")}
      </a>
    </p>
  );
}
