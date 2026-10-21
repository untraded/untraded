// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { CodeFieldLabels, CodesLabels } from "@/components/codes-form";

/** The codes form's texts, from the messages (it is a client component). */
export async function codesLabels(): Promise<CodesLabels> {
  const t = await getTranslations("codes");
  const field = (name: "auth" | "share"): CodeFieldLabels => ({
    label: t(`${name}.label`),
    formatHint: t(`${name}.formatHint`),
    help: t(`${name}.help`),
    other: t(`${name}.other`),
    format: t(`${name}.format`),
    refused: t(`${name}.refused`),
  });
  return {
    auth_code: field("auth"),
    share_code: field("share"),
    helpLink: t("helpLink"),
    map: {
      caption: t("map.caption"),
      note: t("map.note"),
      auth: t("map.auth"),
      create: t("map.create"),
      share: t("map.share"),
    },
    submit: t("submit"),
    pending: t("pending"),
    errors: {
      consent: t("errorConsent"),
      unavailable: t("errorUnavailable"),
      failed: t("errorFailed"),
    },
  };
}
