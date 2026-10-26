## What and why

## Checklist

- [ ] `just check` passes locally
- [ ] Tests added or updated
- [ ] For metrics: spec updated in `docs/metrics-v1.md`, version bumped if the formula changed (with its line in `untraded.metrics.notes.CHANGES`), `just docs` run (and `just fixtures-expect` for an intended change), the changes of `expected_metrics.json` and `docs/metrics/` explained
- [ ] For the web app: new strings in every language (`apps/web/messages/en.json` and `fr.json`)
- [ ] For the database: a new migration in `db/`, never an edit of an applied one
- [ ] SPDX header on new source files
