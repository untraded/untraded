// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const config: NextConfig = {
  // A self-contained server for the container image (deployment PR).
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    // The browser keeps a visited dynamic page for 30 s, so going back and forth between pages
    // does not ask the server again each time. Every server action that changes data calls
    // `revalidatePath` or sets a cookie, and `router.refresh()` (upload, time zone) clears it too:
    // only data written elsewhere (a match the worker just parsed) can show up to 30 s late, which
    // a reload settles. Long enough to cover browsing, short enough to stay current.
    staleTimes: { dynamic: 30 },
  },
  // The formulas pages read `docs/metrics/` of the repository at run time: ship them beside the
  // standalone server (`src/lib/metric-docs-files.ts`).
  outputFileTracingIncludes: {
    "/formulas": ["../../docs/metrics/*.md"],
    "/formulas/[id]": ["../../docs/metrics/*.md"],
  },
  // Our radars (`public/radars/`) change only when they are redrawn, after a map update: a day in
  // the browser, then a week served while it checks for a new one (`docs/replay-format.md`). The
  // landing page's screenshots (`public/showcase/`) and the icons (`public/icons/`) change as
  // rarely, and get the same rule.
  async headers() {
    return ["/radars/:file*", "/showcase/:file*", "/icons/:file*"].map((source) => ({
      source,
      headers: [
        { key: "Cache-Control", value: "public, max-age=86400, stale-while-revalidate=604800" },
      ],
    }));
  },
};

export default createNextIntlPlugin("./src/i18n/request.ts")(config);
