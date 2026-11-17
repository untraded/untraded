// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { RAIL_CLIP, RAIL_TOOLTIP } from "./nav";

/** The account trigger's look, shared by the stand-in and the real menu trigger so that swapping
 * one for the other changes nothing on screen. At the foot of the rail: the initial alone, the
 * name in a tooltip; unfolded, the name beside it. The initial keeps its place in both states. */
export const ACCOUNT_TRIGGER_CLASS =
  "group/nav relative flex h-10 w-full touch-rail:h-12 shrink-0 items-center rounded-md px-[7px] text-left text-chrome-foreground hover:bg-muted aria-expanded:bg-muted touch-rail:justify-center touch-rail:px-0";

export function AccountTriggerFace({ name }: { name: string }) {
  return (
    <>
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-sm bg-muted text-sm font-semibold uppercase"
      >
        {name.slice(0, 1)}
      </span>
      {/* The trigger's own label names it: the name is for the eye. Nothing of it on a touch
          screen's folded rail. */}
      <span aria-hidden="true" className={cn(RAIL_CLIP, "flex items-center touch-rail:hidden")}>
        <span className="min-w-0 truncate pl-2.5 text-sm font-semibold">{name}</span>
        <ChevronsUpDown className="ml-auto size-4 shrink-0 text-chrome-muted" />
      </span>
      <span aria-hidden="true" className={RAIL_TOOLTIP}>
        {name}
      </span>
    </>
  );
}
