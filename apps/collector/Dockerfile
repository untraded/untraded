# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
#
# The collector. Build context: the repository root (pnpm workspace). No native modules: builds
# on amd64 and arm64.

FROM node:24-bookworm-slim

WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY apps/collector/package.json apps/collector/
RUN pnpm install --frozen-lockfile --prod --filter @untraded/collector
COPY apps/collector/ apps/collector/

# Named volumes inherit this ownership on first mount.
RUN mkdir -p /data && chown node:node /data
USER node
WORKDIR /app/apps/collector
ENV COLLECTOR_DATA_DIR=/data
CMD ["./node_modules/.bin/tsx", "src/main.ts", "run"]
