// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useRef } from "react";
import { lazyModule } from "@/lib/lazy";
import { useLazyPopup } from "./lazy-popup";
import { useCurrentSpace } from "./space";
import { SPACE_TRIGGER_CLASS, type SpaceLink, SpaceTriggerFace } from "./space-trigger";

export interface SpaceMenuProps {
  /** The player's own space first, then their teams. */
  spaces: SpaceLink[];
  /** The menu's title ("Workspaces"). */
  title: string;
}

const popup = lazyModule(() => import("./space-menu-popup").then((m) => m.SpaceMenuPopup));

/** The switch at the head of the rail: the open space, and a menu of the others. The menu's code
 * loads on first use, as the account menu's does. */
export function SpaceMenu(props: SpaceMenuProps) {
  const standIn = useRef<HTMLButtonElement>(null);
  const { Component, start, preload, open } = useLazyPopup(popup, standIn);
  const current = useCurrentSpace(props.spaces);
  if (!current) return null;
  if (Component) return <Component {...props} {...start} />;
  return (
    <button
      ref={standIn}
      type="button"
      aria-label={current.label}
      aria-haspopup="menu"
      aria-expanded={false}
      className={SPACE_TRIGGER_CLASS}
      onPointerEnter={preload}
      onFocus={preload}
      onClick={open}
    >
      <SpaceTriggerFace space={current} />
    </button>
  );
}
