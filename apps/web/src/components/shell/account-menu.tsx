// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { ChevronsUpDown, LogOut } from "lucide-react";
import { useTransition } from "react";
import { signOut } from "@/app/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SIDEBAR_LABEL } from "./nav";

/** The workspace at the top of the sidebar: the player's own today, their teams later. */
export function AccountMenu({
  name,
  labels,
}: {
  name: string;
  /** `workspace` is the trigger's accessible name, e.g. "Workspace: name, personal". */
  labels: { workspace: string; personal: string; signOut: string };
}) {
  const [, startTransition] = useTransition();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={labels.workspace}
        className="flex w-full items-center gap-2.5 rounded-md border border-border p-1.5 text-left hover:bg-muted lg:group-data-[collapsed=true]/shell:border-transparent max-lg:border-transparent max-lg:justify-center lg:group-data-[collapsed=true]/shell:justify-center"
      >
        <span
          aria-hidden="true"
          className="grid size-7 shrink-0 place-items-center rounded-sm bg-muted text-sm font-semibold uppercase"
        >
          {name.slice(0, 1)}
        </span>
        <span className={`${SIDEBAR_LABEL} min-w-0 leading-tight`}>
          <span className="block truncate text-sm font-semibold">{name}</span>
          <span className="block text-xs text-muted-foreground">{labels.personal}</span>
        </span>
        <ChevronsUpDown
          aria-hidden="true"
          className="ml-auto hidden size-4 text-muted-foreground lg:block lg:group-data-[collapsed=true]/shell:hidden"
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-48">
        <DropdownMenuItem onClick={() => startTransition(() => signOut())}>
          <LogOut aria-hidden="true" />
          {labels.signOut}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
