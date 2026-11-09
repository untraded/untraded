// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { RAIL_TOOLTIP } from "./nav";

/** The account trigger's look, shared by the stand-in and the real menu trigger so that swapping
 * one for the other changes nothing on screen. At the foot of the rail: the initial alone, the
 * name in a tooltip; unfolded, the name beside it. */
export const ACCOUNT_TRIGGER_CLASS =
  "group/nav relative flex h-10 w-full shrink-0 items-center justify-center gap-2.5 rounded-md text-left text-chrome-foreground hover:bg-muted aria-expanded:bg-muted md:group-data-[collapsed=false]/shell:justify-start md:group-data-[collapsed=false]/shell:px-1.5";

export function AccountTriggerFace({ name }: { name: string }) {
  return (
    <>
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-sm bg-muted text-sm font-semibold uppercase"
      >
        {name.slice(0, 1)}
      </span>
      <span
        className={cn(
          RAIL_TOOLTIP,
          "md:group-data-[collapsed=false]/shell:min-w-0 md:group-data-[collapsed=false]/shell:truncate md:group-data-[collapsed=false]/shell:text-sm md:group-data-[collapsed=false]/shell:font-semibold",
        )}
      >
        {name}
      </span>
      <ChevronsUpDown
        aria-hidden="true"
        className={cn(
          "ml-auto hidden size-4 text-chrome-muted md:group-data-[collapsed=false]/shell:block",
        )}
      />
    </>
  );
}
