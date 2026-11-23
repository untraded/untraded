// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Button } from "@/components/ui/button";
import { install } from "@/lib/install";
import { useCanInstall } from "./use-install";

/** The settings' "App" line, drawn like its neighbours: only where the browser can install the
 * site (or explain how, on an iPhone), and not once installed. */
export function InstallSetting({
  labels,
}: {
  labels: { title: string; hint: string; install: string };
}) {
  if (!useCanInstall()) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2.5 border-t border-line-soft px-3.5 py-3 first:border-t-0">
      <div className="min-w-0">
        <h3 className="text-sm font-semibold">{labels.title}</h3>
        <p className="text-[0.8125rem] text-muted-foreground">{labels.hint}</p>
      </div>
      <Button variant="outline" size="sm" onClick={() => void install()}>
        {labels.install}
      </Button>
    </div>
  );
}
