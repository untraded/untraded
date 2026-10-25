# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
#
# The worker, and the database migrations (`untraded-db upgrade`), in one image.
# Build context: the repository root (uv workspace). Builds on amd64 and arm64.

FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

FROM python:3.14-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY . .
RUN uv sync --frozen --no-dev --no-editable --package untraded-worker \
    && rm -rf /root/.cache /src

RUN useradd --create-home --uid 1000 untraded && mkdir -p /data/store /data/uploads \
    && chown -R untraded /data
USER untraded
WORKDIR /data
ENV UNTRADED_STORE_DIR=/data/store UNTRADED_UPLOADS_DIR=/data/uploads
CMD ["untraded-worker", "run"]
