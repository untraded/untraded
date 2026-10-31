// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { PanelLeft } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SIDEBAR_COOKIE } from "@/i18n/locale";

/** Folds the sidebar to its icons, or unfolds it. The choice is kept in a cookie, so the server
 * renders the next page the same way (no jump on load). */
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
      className="hidden text-muted-foreground lg:inline-flex"
      aria-label={label}
      title={label}
      aria-expanded={!collapsed}
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
    </Button>
  );
}
