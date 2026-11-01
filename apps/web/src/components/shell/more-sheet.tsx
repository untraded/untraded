// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useRef } from "react";
import { lazyModule } from "@/lib/lazy";
import { useLazyPopup } from "./lazy-popup";
import { MORE_TRIGGER_CLASS, MoreTriggerFace } from "./more-trigger";

export interface MoreSheetProps {
  /** `admin` is null for players who are not admins: no entry then. */
  labels: {
    more: string;
    settings: string;
    progress: string;
    upload: string;
    formulas: string;
    admin: string | null;
    /** The team mode preview, admins only too, with its badge. */
    team: string | null;
    preview: string;
    signOut: string;
  };
}

const popup = lazyModule(() => import("./more-sheet-popup").then((m) => m.MoreSheetPopup));

/** The phone's fourth tab: a panel with what does not fit in the tab bar. The panel's code loads
 * on first use. */
export function MoreSheet(props: MoreSheetProps) {
  const standIn = useRef<HTMLButtonElement>(null);
  const { Component, start, preload, open } = useLazyPopup(popup, standIn);
  if (Component) return <Component {...props} {...start} />;
  return (
    <button
      ref={standIn}
      type="button"
      aria-haspopup="dialog"
      aria-expanded={false}
      className={MORE_TRIGGER_CLASS}
      onPointerEnter={preload}
      onFocus={preload}
      onClick={open}
    >
      <MoreTriggerFace label={props.labels.more} />
    </button>
  );
}
