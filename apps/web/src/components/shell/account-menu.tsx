// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useRef } from "react";
import { lazyModule } from "@/lib/lazy";
import { ACCOUNT_TRIGGER_CLASS, AccountTriggerFace } from "./account-trigger";
import { useLazyPopup } from "./lazy-popup";

/** A workspace the menu switches to: the player's own space, or one of their teams. */
export interface WorkspaceLink {
  key: string;
  name: string;
  href: string;
  team: boolean;
}

export interface AccountMenuProps {
  name: string;
  /** The player's space and their teams; empty when they have no team (no switch then). */
  workspaces: WorkspaceLink[];
  /** `account` is the trigger's accessible name, e.g. "Account: name". */
  labels: { account: string; settings: string; signOut: string; workspace: string };
}

const popup = lazyModule(() => import("./account-menu-popup").then((m) => m.AccountMenuPopup));

/** The account at the foot of the rail: who is signed in, the switch between their own space and
 * their teams, the settings, signing out. The menu's code loads on first use. */
export function AccountMenu(props: AccountMenuProps) {
  const standIn = useRef<HTMLButtonElement>(null);
  const { Component, start, preload, open } = useLazyPopup(popup, standIn);
  if (Component) return <Component {...props} {...start} />;
  return (
    <button
      ref={standIn}
      type="button"
      aria-label={props.labels.account}
      aria-haspopup="menu"
      aria-expanded={false}
      className={ACCOUNT_TRIGGER_CLASS}
      onPointerEnter={preload}
      onFocus={preload}
      onClick={open}
    >
      <AccountTriggerFace name={props.name} />
    </button>
  );
}
