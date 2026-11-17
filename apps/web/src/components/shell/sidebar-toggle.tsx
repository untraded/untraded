// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { PanelLeft } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SIDEBAR_COOKIE } from "@/i18n/locale";
import { cn } from "@/lib/cn";
import { RAIL_MOTION, TOOLTIP } from "./nav";

/** Shows the rail's labels beside its icons, or folds them back into tooltips. The choice is kept
 * in a cookie, so the server renders the next page the same way (no jump on load). */
export function SidebarToggle({
  collapsed: initial,
  labels,
  tall = false,
}: {
  collapsed: boolean;
  labels: { collapse: string; expand: string };
  /** Under the workspace switch, which is taller than the logo: lower on a touch screen, and
   * centred on its 44 px when the rail is unfolded. */
  tall?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(initial);
  const label = collapsed ? labels.expand : labels.collapse;
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      // Under the sign when the rail is folded, at the right of the logo when it is unfolded: it
      // travels from one place to the other with the rail's edge.
      className={cn(
        "group/nav absolute top-10 left-[calc(50%-14px)] hidden text-chrome-muted transition-[top,left,color,background-color,border-color,box-shadow] touch-rail:left-[calc(50%-20px)] touch-rail:size-10 hover:text-chrome-foreground md:inline-flex md:group-data-[collapsed=false]/shell:top-0.5 md:group-data-[collapsed=false]/shell:left-[calc(100%-28px)]",
        tall && "touch-rail:top-[52px] md:group-data-[collapsed=false]/shell:top-2",
        RAIL_MOTION,
      )}
      // The label says what a press does; it changes with the state, so no `aria-expanded` too.
      aria-label={label}
      onClick={(event) => {
        const next = !collapsed;
        setCollapsed(next);
        event.currentTarget
          .closest("[data-collapsed]")
          ?.setAttribute("data-collapsed", String(next));
        // biome-ignore lint/suspicious/noDocumentCookie: a plain preference, read by the server.
        document.cookie = `${SIDEBAR_COOKIE}=${next ? "collapsed" : "expanded"}; path=/; max-age=31536000; samesite=lax`;
      }}
    >
      <PanelLeft aria-hidden="true" />
      <span aria-hidden="true" className={`${TOOLTIP} touch-rail:hidden`}>
        {label}
      </span>
    </Button>
  );
}
