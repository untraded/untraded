// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Ellipsis, LogOut } from "lucide-react";
import Link from "next/link";
import { useState, useTransition } from "react";
import { signOut } from "@/app/actions";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { SECTIONS } from "./nav";

/** The phone's fourth tab: a panel with what does not fit in the tab bar. */
export function MoreSheet({
  labels,
}: {
  labels: { more: string; settings: string; signOut: string };
}) {
  const [open, setOpen] = useState(false);
  const [, startTransition] = useTransition();
  const Settings = SECTIONS.settings.icon;
  const row =
    "flex h-11 w-full items-center gap-3 rounded-md px-3 text-[0.9375rem] hover:bg-muted [&_svg]:size-[18px] [&_svg]:text-muted-foreground";
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="flex flex-col items-center gap-0.5 pt-2 pb-1 text-[0.6875rem] text-muted-foreground aria-expanded:text-foreground">
        <Ellipsis aria-hidden="true" className="size-5" />
        {labels.more}
      </SheetTrigger>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="gap-1 rounded-t-xl px-3 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <div aria-hidden="true" className="mx-auto mb-2 h-1 w-9 rounded-full bg-border" />
        <SheetTitle className="sr-only">{labels.more}</SheetTitle>
        <Link href={SECTIONS.settings.href} className={row} onClick={() => setOpen(false)}>
          <Settings aria-hidden="true" />
          {labels.settings}
        </Link>
        <button type="button" className={row} onClick={() => startTransition(() => signOut())}>
          <LogOut aria-hidden="true" />
          {labels.signOut}
        </button>
      </SheetContent>
    </Sheet>
  );
}
