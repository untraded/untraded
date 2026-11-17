// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { LazyStart } from "./lazy-popup";
import { useCurrentSpace } from "./space";
import type { SpaceMenuProps } from "./space-menu";
import { SPACE_BAR_CLASS, SpaceBadge, SpaceBarFace } from "./space-trigger";

/** The phone's workspace sheet itself, loaded by `SpaceSheet` on first use. */
export function SpaceSheetPopup({
  spaces,
  title,
  defaultOpen,
  focusTrigger,
}: SpaceMenuProps & LazyStart) {
  const [open, setOpen] = useState(defaultOpen);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusTrigger) trigger.current?.focus();
  }, [focusTrigger]);
  const current = useCurrentSpace(spaces);
  if (!current) return null;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger ref={trigger} aria-label={current.label} className={SPACE_BAR_CLASS}>
        <SpaceBarFace space={current} />
      </SheetTrigger>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="gap-1 rounded-t-xl px-3 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <div aria-hidden="true" className="mx-auto mb-2 h-1 w-9 rounded-full bg-border" />
        <SheetTitle className="px-2 pb-1 text-[0.8125rem] font-normal text-muted-foreground">
          {title}
        </SheetTitle>
        {spaces.map((space) => {
          const here = space.key === current.key;
          return (
            <Link
              key={space.key}
              href={space.href}
              aria-current={here ? "true" : undefined}
              onClick={() => setOpen(false)}
              className="flex min-h-13 items-center gap-3 rounded-md px-2.5 text-[0.9375rem] hover:bg-muted aria-[current=true]:bg-muted aria-[current=true]:font-semibold"
            >
              <SpaceBadge space={space} className="size-8 text-xs" />
              <span className="min-w-0 flex-1 truncate">{space.menuName}</span>
              {space.role && (
                <span className="shrink-0 text-xs font-normal text-muted-foreground">
                  {space.role}
                </span>
              )}
              <Check
                aria-hidden="true"
                className={here ? "size-[18px] shrink-0 text-highlight" : "invisible size-[18px]"}
              />
            </Link>
          );
        })}
      </SheetContent>
    </Sheet>
  );
}
