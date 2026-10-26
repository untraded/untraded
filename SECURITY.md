# Security policy

Untraded handles Steam credentials (bot accounts), match history authentication codes, sign-in sessions, demo files players send and personal match data. We take vulnerabilities seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private vulnerability reporting: *Security → Report a vulnerability* on this repository. We aim to acknowledge reports within 72 hours.

## Scope

- Leaks of secrets (bot credentials, refresh tokens, authentication codes, the key that encrypts them, API keys, session tokens).
- Access control: what a signed-in player may see or change (row-level security, workspaces, admin routes, invitations).
- Ingestion: demo uploads (`POST /uploads`) and demo downloads (the worker only reaches public addresses unless told otherwise).
- Consent and erasure: data kept after a player withdraws or asks to be erased.

## Supported versions

During the pre-1.0 period, fixes go to `main` (the services in `apps/`, run from source) and to the latest release of the `untraded` packages.
