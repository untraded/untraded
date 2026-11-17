// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Teams on the site: who may do what, as the API decides it (`docs/contrat-api-equipes.md` in the
// HQ). The site only hides what a role may not do; the API refuses it anyway.

import type { Me, Role, TeamPermission, WorkspaceRef } from "./api";

/** The four roles every team starts with: the site translates their names. */
export const DEFAULT_ROLES = ["owner", "coach", "player", "viewer"] as const;
export type DefaultRole = (typeof DEFAULT_ROLES)[number];

export function isDefaultRole(name: string): name is DefaultRole {
  return (DEFAULT_ROLES as readonly string[]).includes(name);
}

/** Whether a role's permissions hold `permission` (`*` holds them all). */
export function allows(permissions: readonly string[], permission: TeamPermission): boolean {
  return permissions.includes("*") || permissions.includes(permission);
}

/** The player's teams, as `/me` lists them (none from an API that predates teams). */
export function teamsOf(me: Pick<Me, "workspaces">): WorkspaceRef[] {
  return (me.workspaces ?? []).filter((w) => w.kind === "team");
}

/**
 * The roles a member may give, to a member or in an invitation: never the owner's, and none with a
 * permission their own role lacks (the API answers `role_too_high` to anything else).
 */
export function assignableRoles(roles: readonly Role[], mine: Role): Role[] {
  return roles.filter(
    (role) =>
      role.name !== "owner" &&
      !role.permissions.includes("*") &&
      (mine.permissions.includes("*") ||
        role.permissions.every((p) => mine.permissions.includes(p))),
  );
}

/** The role invitations start from: Player when it may be given, else the first that may. */
export function defaultInviteRole(roles: readonly Role[]): Role | undefined {
  return roles.find((r) => r.name === "player") ?? roles[0];
}

/** A team's address on the site, or one of its pages. */
export function teamHref(slug: string, page?: "members" | "matches" | "upload" | "review"): string {
  return `/teams/${encodeURIComponent(slug)}${page ? `/${page}` : ""}`;
}

/** A team's match, on the team's pages. */
export function teamMatchHref(slug: string, id: string): string {
  return `${teamHref(slug, "matches")}/${encodeURIComponent(id)}`;
}

/** Whether a role reads the team's matches (its matches pages and its home's). */
export function readsMatches(permissions: readonly string[]): boolean {
  return allows(permissions, "matches.read");
}

/** The address an invitation link opens, on this site. */
export function joinPath(token: string): string {
  return `/join/${encodeURIComponent(token)}`;
}

/** An invitation token the site will pass on: URL-safe characters only, so that it can never
 * be a path segment such as `..`. */
export function validToken(token: string): boolean {
  return /^[A-Za-z0-9_-]{8,256}$/.test(token);
}

/** A team slug, as the API takes it (`[a-z0-9-]{3,32}`, never the personal `u-<digits>`). */
export function validSlug(slug: string): boolean {
  return /^[a-z0-9-]{3,32}$/.test(slug) && !/^u-\d+$/.test(slug);
}

/** A team address segment the site will ask the API about: a slug's characters, nothing else
 * (the API answers 404 to the rest). */
export function validTeamParam(slug: string): boolean {
  return /^[A-Za-z0-9-]{1,64}$/.test(slug);
}
