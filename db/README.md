# untraded-db

Database migrations of the Untraded services (ADR [0006](../docs/adr/0006-schema-ownership.md) and [0011](../docs/adr/0011-phase-2-database-schema.md)). The schema is owned by Python: every change is an Alembic migration here, and the Node services read the types generated from the live schema.

```bash
just db-up        # PostgreSQL 16 for development (compose.dev.yaml)
just db-migrate   # apply every migration
just db-down      # stop it (the data volume is kept)
```

The connection comes from `UNTRADED_DATABASE_URL`, for example `postgresql+psycopg://untraded:untraded@localhost:5432/untraded`, the development default.

- **Migration 0001** is the reference schema validated in ADR 0011, frozen: `docs/db/schema.sql` must stay identical to it, which a test checks.
- **Later changes** are new migrations, never edits of an applied one.
- **CI** applies every migration to PostgreSQL 16, then runs the tenant isolation check `docs/db/rls-check.sql`.
