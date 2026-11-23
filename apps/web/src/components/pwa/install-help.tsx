// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { type ReactNode, useEffect, useState } from "react";
import { claimInstallOffer, setHelpOpen } from "@/lib/install";
import { lazyModule } from "@/lib/lazy";
import { useHelpOpen } from "./use-install";

// This module comes with the signed-in shell, whose controls offer the install from now on.
claimInstallOffer();

export interface InstallHelpLabels {
  title: string;
  lead: string;
  share: ReactNode;
  add: ReactNode;
  done: string;
  close: string;
}

const sheet = lazyModule(() => import("./install-help-sheet").then((m) => m.InstallHelpSheet));

/**
 * The iPhone's install help, one for the whole shell: any "Install the app" control opens it on
 * an iPhone or iPad. Its code (the sheet) loads the first time it opens, then stays mounted so
 * that it closes with its animation.
 */
export function InstallHelp({ labels }: { labels: InstallHelpLabels }) {
  const open = useHelpOpen();
  const [Sheet, setSheet] = useState(() => sheet.current);
  useEffect(() => {
    if (!open || Sheet) return;
    sheet.load().then(
      (Component) => setSheet(() => Component),
      () => setHelpOpen(false),
    );
  }, [open, Sheet]);
  if (!Sheet) return null;
  return <Sheet open={open} labels={labels} />;
}
