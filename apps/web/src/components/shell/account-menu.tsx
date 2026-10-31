// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { ChevronsUpDown, LogOut } from "lucide-react";
import Link from "next/link";
import { useTransition } from "react";
import { signOut } from "@/app/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SECTIONS, SIDEBAR_LABEL } from "./nav";

/** The account at the top of the sidebar: who is signed in, the settings, signing out. A team
 * workspace switch belongs here once teams exist. */
export function AccountMenu({
  name,
  labels,
}: {
  name: string;
  /** `account` is the trigger's accessible name, e.g. "Account: name". */
  labels: { account: string; settings: string; signOut: string };
}) {
  const [, startTransition] = useTransition();
  const Settings = SECTIONS.settings.icon;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={labels.account}
        className="flex w-full items-center gap-2.5 rounded-md border border-border p-1.5 text-left hover:bg-muted lg:group-data-[collapsed=true]/shell:border-transparent max-lg:border-transparent max-lg:justify-center lg:group-data-[collapsed=true]/shell:justify-center"
      >
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
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-48">
        <DropdownMenuItem render={<Link href={SECTIONS.settings.href} />}>
          <Settings aria-hidden="true" />
          {labels.settings}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => startTransition(() => signOut())}>
          <LogOut aria-hidden="true" />
          {labels.signOut}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
