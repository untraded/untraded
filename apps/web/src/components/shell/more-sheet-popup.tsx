// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, useTransition } from "react";
import { signOut } from "@/app/actions";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { LazyStart } from "./lazy-popup";
import type { MoreSheetProps } from "./more-sheet";
import { MORE_TRIGGER_CLASS, MoreTriggerFace } from "./more-trigger";
import { SECTIONS } from "./nav";
import { PreviewBadge } from "./preview-badge";

/** The "More" panel itself, loaded by `MoreSheet` on first use. */
export function MoreSheetPopup({ labels, defaultOpen, focusTrigger }: MoreSheetProps & LazyStart) {
  const [open, setOpen] = useState(defaultOpen);
  const [, startTransition] = useTransition();
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusTrigger) trigger.current?.focus();
  }, [focusTrigger]);
  const Settings = SECTIONS.settings.icon;
  const Admin = SECTIONS.admin.icon;
  const Team = SECTIONS.team.icon;
  const Formulas = SECTIONS.formulas.icon;
  const Send = SECTIONS.upload.icon;
  const Trend = SECTIONS.progress.icon;
  const row =
    "flex h-11 w-full items-center gap-3 rounded-md px-3 text-[0.9375rem] hover:bg-muted [&_svg]:size-[18px] [&_svg]:text-muted-foreground";
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger ref={trigger} className={MORE_TRIGGER_CLASS}>
        <MoreTriggerFace label={labels.more} />
      </SheetTrigger>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="gap-1 rounded-t-xl px-3 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <div aria-hidden="true" className="mx-auto mb-2 h-1 w-9 rounded-full bg-border" />
        <SheetTitle className="sr-only">{labels.more}</SheetTitle>
        <Link href={SECTIONS.progress.href} className={row} onClick={() => setOpen(false)}>
          <Trend aria-hidden="true" />
          {labels.progress}
        </Link>
        <Link href={SECTIONS.upload.href} className={row} onClick={() => setOpen(false)}>
          <Send aria-hidden="true" />
          {labels.upload}
        </Link>
        {labels.team && (
          <Link href={SECTIONS.team.href} className={row} onClick={() => setOpen(false)}>
            <Team aria-hidden="true" />
            {labels.team}
            <PreviewBadge label={labels.preview} />
          </Link>
        )}
        <div aria-hidden="true" className="mx-3 my-1 border-t border-border" />
        <Link href={SECTIONS.formulas.href} className={row} onClick={() => setOpen(false)}>
          <Formulas aria-hidden="true" />
          {labels.formulas}
        </Link>
        <Link href={SECTIONS.settings.href} className={row} onClick={() => setOpen(false)}>
          <Settings aria-hidden="true" />
          {labels.settings}
        </Link>
        {labels.admin && (
          <Link href={SECTIONS.admin.href} className={row} onClick={() => setOpen(false)}>
            <Admin aria-hidden="true" />
            {labels.admin}
          </Link>
        )}
        <button type="button" className={row} onClick={() => startTransition(() => signOut())}>
          <LogOut aria-hidden="true" />
          {labels.signOut}
        </button>
      </SheetContent>
    </Sheet>
  );
}
