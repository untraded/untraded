// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { Suspense } from "react";
import { LineupsView } from "@/components/team/lineups-view";

/** The view reads `?map=` and `?open=` (a link from an exec): under a boundary, as Next asks. */
export default function Page() {
  return (
    <Suspense>
      <LineupsView />
    </Suspense>
  );
}
