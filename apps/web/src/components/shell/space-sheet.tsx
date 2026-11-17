// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useRef } from "react";
import { lazyModule } from "@/lib/lazy";
import { useLazyPopup } from "./lazy-popup";
import { useCurrentSpace } from "./space";
import type { SpaceMenuProps } from "./space-menu";
import { SPACE_BAR_CLASS, SpaceBarFace } from "./space-trigger";

const popup = lazyModule(() => import("./space-sheet-popup").then((m) => m.SpaceSheetPopup));

/** The phone's switch, in the top bar: the open space, and a sheet of the others. The sheet's
 * code loads on first use, as the "More" sheet's does. */
export function SpaceSheet(props: SpaceMenuProps) {
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
      aria-haspopup="dialog"
      aria-expanded={false}
      className={SPACE_BAR_CLASS}
      onPointerEnter={preload}
      onFocus={preload}
      onClick={open}
    >
      <SpaceBarFace space={current} />
    </button>
  );
}
