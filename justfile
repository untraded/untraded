# Run `just` to list recipes.

# Windows has no `sh`: run recipes with PowerShell there (Linux/macOS keep sh).
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

# Install Python and TypeScript dependencies
install:
    uv sync --all-packages
    pnpm install

# Everything CI runs
check: lint typecheck test reuse

# Lint and format check (no changes)
lint:
    uv run ruff check .
    uv run ruff format --check .
    pnpm lint

# Auto-format and auto-fix
fmt:
    uv run ruff check --fix .
    uv run ruff format .
    pnpm fmt

# Type-check Python (mypy --strict) and TypeScript
typecheck:
    uv run mypy
    pnpm typecheck

# Run all tests
test:
    uv run pytest
    pnpm test

# Verify every file declares its license (REUSE)
reuse:
    uv run reuse lint

# Build publishable packages
build:
    uv build --package untraded --out-dir dist/py
    pnpm build

# Spike S0.1: fetch new Valve matches once (reads spikes/S0.1-valve/.env)
spike-valve:
    pnpm --filter s0.1-valve start

# Spike S0.3: local server receiving FACEIT demo URLs from the extension (127.0.0.1:8765)
spike-faceit-server:
    uv run --package s0-3-faceit-extension python spikes/S0.3-faceit-extension/server.py

# Spike S0.2: inspect and benchmark every demo in a directory
spike-parsing dir:
    uv run --package s0-2-parsing python spikes/S0.2-parsing/inspect_demos.py {{dir}}

# Spike S0.4: check round cutting in every .dem of a directory (pro demos)
spike-rounds dir:
    uv run --package s0-2-parsing python spikes/S0.4-pro/check_rounds.py {{dir}}

# Spike S0.6: storage and CPU cost per match for every demo in one or more directories
spike-costs +dirs:
    uv run --package s0-2-parsing python spikes/S0.6-costs/measure.py {{dirs}}
