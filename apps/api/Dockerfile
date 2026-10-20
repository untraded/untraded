# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
#
# The API. Build context: the repository root (uv workspace). Builds on amd64 and arm64.

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
RUN uv sync --frozen --no-dev --no-editable --package untraded-api \
    && rm -rf /root/.cache /src

RUN useradd --create-home --uid 1000 untraded
USER untraded
WORKDIR /home/untraded
EXPOSE 8000
CMD ["untraded-api", "--host", "0.0.0.0", "--port", "8000"]
