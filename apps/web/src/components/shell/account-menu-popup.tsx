// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useTransition } from "react";
import { signOut } from "@/app/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AccountMenuProps } from "./account-menu";
import { ACCOUNT_TRIGGER_CLASS, AccountTriggerFace } from "./account-trigger";
import type { LazyStart } from "./lazy-popup";
import { SECTIONS } from "./nav";

/** The account menu itself, loaded by `AccountMenu` on first use. */
export function AccountMenuPopup({
  name,
  workspaces,
  labels,
  defaultOpen,
  focusTrigger,
}: AccountMenuProps & LazyStart) {
  const [, startTransition] = useTransition();
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusTrigger) trigger.current?.focus();
  }, [focusTrigger]);
  const pathname = usePathname();
  const Settings = SECTIONS.settings.icon;
  // The current workspace: the team whose pages are open, else the player's own space.
  const current =
    workspaces.find((w) => w.team && (pathname === w.href || pathname.startsWith(`${w.href}/`)))
      ?.key ?? "personal";
  return (
    <DropdownMenu defaultOpen={defaultOpen}>
      <DropdownMenuTrigger
        ref={trigger}
        aria-label={labels.account}
        className={ACCOUNT_TRIGGER_CLASS}
      >
        <AccountTriggerFace name={name} />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end" sideOffset={8} className="min-w-48">
        {workspaces.length > 0 && (
          <>
            <DropdownMenuGroup>
              <DropdownMenuLabel>{labels.workspace}</DropdownMenuLabel>
              {workspaces.map((w) => (
                <DropdownMenuItem
                  key={w.key}
                  render={
                    <Link
                      href={w.href}
                      aria-current={w.key === current ? "true" : undefined}
                      className="max-w-64"
                    />
                  }
                >
                  <Check
                    aria-hidden="true"
                    className={w.key === current ? "text-highlight" : "invisible"}
                  />
                  <span className="min-w-0 truncate">{w.name}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
          </>
        )}
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
