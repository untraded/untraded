// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronsUpDown } from "lucide-react";
import { SIDEBAR_LABEL } from "./nav";

/** The account trigger's look, shared by the stand-in and the real menu trigger so that swapping
 * one for the other changes nothing on screen. */
export const ACCOUNT_TRIGGER_CLASS =
  "flex w-full items-center gap-2.5 rounded-md border border-border p-1.5 text-left hover:bg-muted lg:group-data-[collapsed=true]/shell:border-transparent max-lg:border-transparent max-lg:justify-center lg:group-data-[collapsed=true]/shell:justify-center";

export function AccountTriggerFace({ name }: { name: string }) {
  return (
    <>
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-sm bg-muted text-sm font-semibold uppercase"
      >
        {name.slice(0, 1)}
      </span>
      <span className={`${SIDEBAR_LABEL} min-w-0 truncate text-sm font-semibold`}>{name}</span>
      <ChevronsUpDown
        aria-hidden="true"
        className="ml-auto hidden size-4 text-muted-foreground lg:block lg:group-data-[collapsed=true]/shell:hidden"
      />
    </>
  );
}
