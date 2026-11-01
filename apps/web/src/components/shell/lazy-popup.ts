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
  const load = useCallback(
    (clicked: boolean) => {
      lazy.load().then(
        (Component) =>
          setLoaded((previous) =>
            // A click can land between a hover's load and its render: it still opens the popup.
            previous && !(wantsOpen.current && !previous.start.defaultOpen)
              ? previous
              : {
                  Component,
                  start: {
                    defaultOpen: wantsOpen.current,
                    focusTrigger:
                      standIn.current !== null && document.activeElement === standIn.current,
                  },
                },
          ),
        () => {
          // The network failed: the stand-in stays, and the next hover or click tries again. A
          // click must not open the popup later on its own; and since the code may be gone for
          // good (a new version deployed since the page loaded), reloading is what a click gets.
          wantsOpen.current = false;
          if (clicked) window.location.reload();
        },
      );
    },
    [lazy, standIn],
  );
  const preload = useCallback(() => load(false), [load]);
  const open = useCallback(() => {
    wantsOpen.current = true;
    load(true);
  }, [load]);
  return {
    Component: loaded?.Component,
    start: loaded?.start ?? { defaultOpen: false, focusTrigger: false },
    preload,
    open,
  };
}
