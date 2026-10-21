// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { CodesLabels } from "@/components/codes-form";

/** The codes form's texts, from the messages (it is a client component). */
export async function codesLabels(): Promise<CodesLabels> {
  const t = await getTranslations("codes");
  return {
    authLabel: t("authLabel"),
    authHelp: t("authHelp"),
    shareLabel: t("shareLabel"),
    shareHelp: t("shareHelp"),
    helpLink: t("helpLink"),
    submit: t("submit"),
    pending: t("pending"),
    errors: {
      auth_code: t("errorAuth"),
      share_code: t("errorShare"),
      consent: t("errorConsent"),
      unavailable: t("errorUnavailable"),
      failed: t("errorFailed"),
    },
  };
}
