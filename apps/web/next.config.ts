// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const config: NextConfig = {
  // A self-contained server for the container image (deployment PR).
  output: "standalone",
  poweredByHeader: false,
};

export default createNextIntlPlugin("./src/i18n/request.ts")(config);
