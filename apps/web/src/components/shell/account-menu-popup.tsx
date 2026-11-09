// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useTransition } from "react";
import { signOut } from "@/app/actions";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AccountMenuProps } from "./account-menu";
import { ACCOUNT_TRIGGER_CLASS, AccountTriggerFace } from "./account-trigger";
import type { LazyStart } from "./lazy-popup";
import { SECTIONS } from "./nav";

/** The account menu itself, loaded by `AccountMenu` on first use. */
export function AccountMenuPopup({
  name,
  labels,
  defaultOpen,
  focusTrigger,
}: AccountMenuProps & LazyStart) {
  const [, startTransition] = useTransition();
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusTrigger) trigger.current?.focus();
  }, [focusTrigger]);
  const Settings = SECTIONS.settings.icon;
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
