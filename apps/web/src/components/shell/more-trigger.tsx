// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Ellipsis } from "lucide-react";

/** The "More" tab's look, shared by the stand-in and the real sheet trigger so that swapping one
 * for the other changes nothing on screen. */
export const MORE_TRIGGER_CLASS =
  "flex flex-col items-center gap-0.5 pt-2 pb-1 text-[0.6875rem] text-muted-foreground aria-expanded:text-foreground";

export function MoreTriggerFace({ label }: { label: string }) {
  return (
    <>
      <Ellipsis aria-hidden="true" className="size-5" />
      {label}
    </>
  );
}
