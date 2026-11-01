// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { type RefObject, useCallback, useRef, useState } from "react";
import type { LazyModule } from "@/lib/lazy";

/** How the real popup mounts once its code is there: open if the trigger was clicked meanwhile,
 * and taking the focus back if the stand-in trigger had it. */
export interface LazyStart {
  defaultOpen: boolean;
  focusTrigger: boolean;
}

/**
 * A menu or a sheet whose code (Base UI, floating-ui) loads on first use rather than with every
 * page. Until then a stand-in button, drawn exactly like the real trigger, sits in its place:
 * pointing at it or focusing it fetches the code, a click also asks for the popup to open as soon
 * as it is there. The real component then replaces the stand-in, with no visible change.
 */
export function useLazyPopup<C>(
  lazy: LazyModule<C>,
  standIn: RefObject<HTMLButtonElement | null>,
): {
  Component: C | undefined;
  start: LazyStart;
  preload: () => void;
  open: () => void;
} {
  const [loaded, setLoaded] = useState<{ Component: C; start: LazyStart } | undefined>(() =>
    lazy.current === undefined
      ? undefined
      : { Component: lazy.current, start: { defaultOpen: false, focusTrigger: false } },
  );
  const wantsOpen = useRef(false);
  const preload = useCallback(() => {
    lazy.load().then(
      (Component) =>
        setLoaded(
          (previous) =>
            previous ?? {
              Component,
              start: {
                defaultOpen: wantsOpen.current,
                focusTrigger:
                  standIn.current !== null && document.activeElement === standIn.current,
              },
            },
        ),
      // The network failed: the stand-in stays, and the next hover or click tries again.
      () => undefined,
    );
  }, [lazy, standIn]);
  const open = useCallback(() => {
    wantsOpen.current = true;
    preload();
  }, [preload]);
  return {
    Component: loaded?.Component,
    start: loaded?.start ?? { defaultOpen: false, focusTrigger: false },
    preload,
    open,
  };
}
