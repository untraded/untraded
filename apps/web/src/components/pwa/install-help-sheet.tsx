// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Share, SquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";
import { setHelpOpen } from "@/lib/install";
import type { InstallHelpLabels } from "./install-help";

/** The two taps that install the app on an iPhone or iPad, in a sheet from the bottom. */
export function InstallHelpSheet({ open, labels }: { open: boolean; labels: InstallHelpLabels }) {
  const step =
    "flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2.5 text-[0.9375rem]";
  return (
    <Sheet open={open} onOpenChange={(next) => setHelpOpen(next)}>
      <SheetContent
        side="bottom"
        closeLabel={labels.close}
        className="mx-auto max-w-md gap-3 rounded-t-xl px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] sm:border-x"
      >
        <div aria-hidden="true" className="mx-auto h-1 w-9 rounded-full bg-border" />
        <div className="pr-8">
          <SheetTitle className="text-base font-semibold">{labels.title}</SheetTitle>
          <SheetDescription className="text-[0.8125rem] text-muted-foreground">
            {labels.lead}
          </SheetDescription>
        </div>
        <ol className="flex flex-col gap-2">
          <li className={step}>
            <span aria-hidden="true" className="font-mono text-xs text-muted-foreground">
              1
            </span>
            <Share aria-hidden="true" className="size-5 shrink-0 text-link" />
            <span>{labels.share}</span>
          </li>
          <li className={step}>
            <span aria-hidden="true" className="font-mono text-xs text-muted-foreground">
              2
            </span>
            <SquarePlus aria-hidden="true" className="size-5 shrink-0 text-link" />
            <span>{labels.add}</span>
          </li>
        </ol>
        <SheetClose render={<Button variant="outline" className="self-start" />}>
          {labels.done}
        </SheetClose>
      </SheetContent>
    </Sheet>
  );
}
