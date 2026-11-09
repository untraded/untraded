// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { PanelLeft } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SIDEBAR_COOKIE } from "@/i18n/locale";
import { TOOLTIP } from "./nav";

/** Shows the rail's labels beside its icons, or folds them back into tooltips. The choice is kept
 * in a cookie, so the server renders the next page the same way (no jump on load). */
export function SidebarToggle({
  collapsed: initial,
  labels,
}: {
  collapsed: boolean;
  labels: { collapse: string; expand: string };
}) {
  const [collapsed, setCollapsed] = useState(initial);
  const label = collapsed ? labels.expand : labels.collapse;
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      className="group/nav relative hidden text-chrome-muted touch-rail:size-10 hover:text-chrome-foreground md:inline-flex"
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
