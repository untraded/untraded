# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
#
# Spike S0.1 in a container: runs the Valve pipeline every SPIKE_INTERVAL_SECONDS.
# Build context is the repository root (pnpm workspace), see compose.yaml.
# No native modules: builds as-is on amd64 and arm64.

FROM node:24-bookworm-slim

WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY spikes/S0.1-valve/package.json spikes/S0.1-valve/
RUN pnpm install --frozen-lockfile --filter s0.1-valve
COPY spikes/S0.1-valve/ spikes/S0.1-valve/

# Named volumes inherit this ownership on first mount.
RUN mkdir -p /data/corpus && chown -R node:node /data
USER node
WORKDIR /app/spikes/S0.1-valve
ENV SPIKE_DATA_DIR=/data \
    UNTRADED_CORPUS_DIR=/data/corpus \
    SPIKE_INTERVAL_SECONDS=3600

# A failed run is logged and retried at the next interval; the loop itself never exits.
CMD ["sh", "-c", "while true; do date -u +'=== %Y-%m-%dT%H:%M:%SZ ==='; ./node_modules/.bin/tsx src/main.ts; sleep \"$SPIKE_INTERVAL_SECONDS\"; done"]
