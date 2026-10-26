# untraded-db

Database migrations of the Untraded services (ADR [0006](../docs/adr/0006-schema-ownership.md) and [0011](../docs/adr/0011-phase-2-database-schema.md)). The schema is owned by Python: every change is an Alembic migration here. The collector (Node) writes plain SQL against it with `pg`.

```bash
just db-up        # PostgreSQL 16 for development (compose.dev.yaml)
just db-migrate   # apply every migration (uv run untraded-db upgrade)
just db-down      # stop it (the data volume is kept)
```

The connection comes from `UNTRADED_DATABASE_URL`, for example `postgresql+psycopg://untraded:untraded@localhost:5432/untraded`, the development default. In `compose.yaml`, the `migrate` service runs `untraded-db upgrade` before the other services start.

| Command | |
|---|---|
| `untraded-db upgrade [revision]` | apply the migrations (default: all, `head`) |
| `untraded-db current` | the revision of the database |
| `untraded-db history` | the migrations |
| `untraded-db revision -m "..."` | write a new empty migration |

| Migration | |
|---|---|
| 0001 | the reference schema of ADR 0011 |
| 0002 | match end times, sign-in sessions, play sessions and their report, the API role `untraded_api` |
| 0003 | which way is an improvement for each metric (`metric_definition.better`) |
| 0004 | references by level (`level_reference`), and which reference a session report used |
| 0005 | advice tied to its session report, and the API's right to record votes |
| 0006 | what each rate stands on, and which metrics can be negative (`metric_definition`) |
| 0007 | what each player agreed to (`consent`, `consent_current`): analysis, and the research corpus |
| 0008 | invitations, the account created at the first sign-in, and the player's own consent and source |
| 0009 | erasing a player: the account marked deleted, the `erase_player` job queued |
| 0010 | demos sent by players: why an upload was refused, and the functions the API records and lists them with |

- **Migration 0001** is the reference schema validated in ADR 0011, frozen: `docs/db/schema.sql` must stay identical to it, which a test checks.
- **Later changes** are new migrations, never edits of an applied one. They form one line from 0001, and each one goes down and up again (`db/tests`).
- **CI** applies every migration to PostgreSQL 16, then runs the tenant isolation check `docs/db/rls-check.sql`.
