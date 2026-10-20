// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { MatchStatus, Result } from "@/lib/api";
import { cn } from "@/lib/cn";

export async function ResultBadge({
  result,
  status,
}: {
  result: Result | null;
  status: MatchStatus;
}) {
  if (status !== "ready" || !result) {
    const t = await getTranslations("status");
    return <span className="text-xs text-zinc-500">{t(status)}</span>;
  }
  const t = await getTranslations("result");
  return (
    <span
      className={cn(
        "rounded px-2 py-0.5 text-xs font-medium",
        result === "win" && "bg-win/15 text-win",
        result === "loss" && "bg-loss/15 text-loss",
        result === "tie" && "bg-zinc-800 text-zinc-300",
      )}
    >
      {t(result)}
    </span>
  );
}
