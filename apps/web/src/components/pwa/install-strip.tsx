// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { AppIcon } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import {
  countVisit,
  install,
  localDay,
  readStripMemory,
  type StripMemory,
  showsStrip,
  writeStripMemory,
} from "@/lib/install";
import { useInstallState } from "./use-install";

export interface InstallStripLabels {
  label: string;
  title: string;
  lead: string;
  install: string;
  dismiss: string;
}

/**
 * The phone's offer to install the app, just above the tabs, in the dark chrome: from the third
 * day the player opens the site, until they install it or close the strip (remembered in this
 * browser). Its button installs (or, on an iPhone, opens the two-tap help, once); either way the
 * strip is then gone for good, and "Install the app" stays in "More" and the settings.
 *
 * It carries `data-install-strip`, by which the page above leaves room for it.
 */
export function InstallStrip({ labels }: { labels: InstallStripLabels }) {
  const state = useInstallState();
  const [memory, setMemory] = useState<StripMemory | null>(null);
  useEffect(() => {
    const counted = countVisit(readStripMemory(), localDay(new Date()));
    writeStripMemory(counted);
    setMemory(counted);
  }, []);
  if (!memory || !showsStrip(state, memory)) return null;
  const close = () => {
    const closed = { ...memory, dismissed: true };
    writeStripMemory(closed);
    setMemory(closed);
    // The strip, and the button that had the focus, are gone: the focus goes to the page.
    document.getElementById("content")?.focus({ preventScroll: true });
  };
  return (
    <section
      data-install-strip
      aria-label={labels.label}
      className="flex items-center gap-3 border-t border-chrome-line py-1.5 pr-1 pl-3"
    >
      <AppIcon className="size-8 shrink-0 rounded-[7px]" />
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-[0.8125rem] font-semibold">{labels.title}</p>
        <p className="text-xs text-chrome-muted">{labels.lead}</p>
      </div>
      <Button
        className="h-9"
        onClick={() => {
          close();
          void install();
        }}
      >
        {labels.install}
      </Button>
      <button
        type="button"
        aria-label={labels.dismiss}
        title={labels.dismiss}
        onClick={close}
        className="grid size-11 shrink-0 place-items-center rounded-md text-chrome-muted outline-none hover:text-chrome-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X aria-hidden="true" className="size-[18px]" />
      </button>
    </section>
  );
}
