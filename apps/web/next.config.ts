// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const config: NextConfig = {
  // A self-contained server for the container image (deployment PR).
  output: "standalone",
  poweredByHeader: false,
  // Our radars (`public/radars/`) change only when they are redrawn, after a map update: a day in
  // the browser, then a week served while it checks for a new one (`docs/replay-format.md`).
  async headers() {
    return [
      {
        source: "/radars/:file*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=86400, stale-while-revalidate=604800" },
        ],
      },
    ];
  },
};

export default createNextIntlPlugin("./src/i18n/request.ts")(config);
