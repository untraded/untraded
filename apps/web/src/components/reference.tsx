// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/i18n/locale";
import type { SessionReport } from "@/lib/api";
import { day, number } from "@/lib/format";

/** What a session is compared to, always named: a short label and the full sentence. */
export async function describeReference(
  reference: SessionReport["reference"],
  locale: Locale,
): Promise<{ short: string | null; sentence: string }> {
  const t = await getTranslations("sessions");
  if (reference.kind === "self") {
    return {
      short: t("refSelf", { matches: reference.matches }),
      sentence: t("reference", {
        matches: reference.matches,
        rounds: reference.rounds,
        since: day(reference.since, locale),
        until: day(reference.until, locale),
      }),
    };
  }
  if (reference.kind === "level") {
    const low = number(reference.level_low, locale);
    const high = number(reference.level_high, locale);
    return {
      short: t("refLevel", { low, high }),
      sentence: t("levelReference", { low, high, matches: reference.matches }),
    };
  }
  return {
    short: null,
    sentence: t("notEnough", {
      minMatches: reference.min_matches,
      minRounds: reference.min_rounds,
      matches: reference.matches,
      rounds: reference.rounds,
    }),
  };
}
