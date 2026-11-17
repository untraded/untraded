# 0012. Team access and permissions

- Status: Accepted
- Date: 2026-11-17
- Builds on: [0011](0011-phase-2-database-schema.md)
- Implemented by: migration 0016 (`db/src/untraded_db/migrations/versions/0016_teams.sql`), `apps/api/src/untraded_api/teams.py`, `apps/worker/src/untraded_worker/team_access.py`

## Context

ADR 0011 put team workspaces, roles with named permissions, rosters and per-player sharing in the schema, but only personal workspaces used them. Filling the team tables as they were would have changed the solo product:

- the match list showed every match row-level security lets the user read, so a team member would have seen the team's matches in their own list;
- the policies of play sessions and aggregates let a workspace that follows a player read them, whatever the player's sharing choice;
- the policies only said "member of the workspace": opening any write on `membership`, `workspace_role` or `workspace_player` would have let a viewer make themselves the owner;
- erasing a team's creator was refused by the worker after the account was closed, so they could no longer sign in to hand the team over.

## Decision

1. **A team is the database's to guard, not the API's.** The API role still has no write privilege on any table. Every change to a team is one `SECURITY DEFINER` function that checks the caller's permission with `has_permission(workspace, permission)` (`*` grants all) and raises a stable code (SQLSTATE `UT001`: `forbidden`, `role_too_high`, `last_owner`, `not_a_member`...) that the API maps to its HTTP errors. A refusal rolls the transaction back.
2. **No escalation.** Whoever has `members.manage` acts only on members whose role is no stronger than theirs (its permissions are a subset of theirs) and gives only such roles, never one with `*`. Ownership moves only by hand-over: the owner and the new owner swap roles, so nobody gains a role they were not given. The last owner can be neither removed nor demoted. Changes to one team's members take its row's lock (`FOR NO KEY UPDATE`), so they happen one at a time.
3. **Default roles** are created with the team: `owner` (`*`), `coach`, `player`, `viewer`. A team has no `created_by`: an admin creates it for its owner, and ownership is the role.
4. **A team sees matches, never coaching.** Play sessions, advice and aggregates are visible to their player only (`own_player`), whichever workspaces follow them. A member's own match list shows their personal workspace's matches (`own`); a team's matches belong to the team's space.
5. **Which matches a team sees** stays materialized in `workspace_match` (ADR 0011), with two changes to `roster`: the 3 roster players must have played **on the same side**, and only players who consent to the analysis count for a roster or share their solo matches. The worker's `refresh_team_access` job recomputes a player's matches whenever their roster rows, membership, sharing choice or consent change; the functions behind those changes queue it. It locks the matches in id order, in one statement, as the analysis locks a match while it writes. `untraded-worker refresh-access` recomputes every match.
6. **Invitation links.** A random token, only its sha256 stored; 7 days; 1 to 20 uses, counted under the link's row lock; revocable; never the owner's role. Opening a link reads only (team name, role, end date). Joining is a `POST` by a signed-in user who has agreed to the current consent text. A valid link also lets a new Steam account into the beta at sign-in; each account it opens counts against its uses (`signups`), so a link opens at most `max_uses` accounts.
7. **Withdrawing the consent leaves every team**, as leaving one does: the memberships end, the roster rows get their end date, nothing is shared any more, and the access is recomputed (`leave_my_teams`, called by the consent route before it records anything). The last owner of a team hands it over first (`owner_must_hand_over`). Joining a team never needs the Steam codes: a signed-in user with the current consent is enough.
8. **Erasure follows teams.** `request_erasure` refuses a team's owner (`owner_must_hand_over`) before anything closes. The worker's erasure removes the player's roster rows (history included) and followed-player rows, and recomputes the teams' access to the matches that stay. Their memberships go with the account.

## Consequences

- A route cannot hand out more than the database allows; a bug in one is at worst a refused call. The rules live in SQL, tested under row-level security as the API role.
- A team loses a match when one of the three players it rested on withdraws their consent or is erased, or when the side rule is not met (2 on one side and 1 on the other no longer counts).
- During the beta a team has one roster; the unique index can be dropped when several rosters are supported.
- Configurable roles (a later screen) reuse the same rule: a team may define roles, never one with `*`.
- Sessions, advice and aggregates of a player are now private to them even inside a workspace that follows them; a future "coach" view of a player's coaching would need its own consent and policy.
