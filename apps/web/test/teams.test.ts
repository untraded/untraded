// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { refusalCode } from "@/lib/api";
import {
  allows,
  assignableRoles,
  defaultInviteRole,
  joinPath,
  teamHref,
  teamsOf,
  validSlug,
  validTeamParam,
} from "@/lib/teams";

const role = (name: string, permissions: string[]) => ({ id: name, name, permissions });
const [OWNER, COACH, PLAYER, VIEWER] = [
  role("owner", ["*"]),
  role("coach", [
    "matches.read",
    "matches.upload",
    "review.comment",
    "review.manage",
    "roster.edit",
    "members.manage",
  ]),
  role("player", ["matches.read", "matches.upload", "review.comment"]),
  role("viewer", ["matches.read"]),
] as const;
const ROLES = [OWNER, COACH, PLAYER, VIEWER];

describe("teams", () => {
  it("reads permissions, `*` holding them all", () => {
    expect(allows(["*"], "team.delete")).toBe(true);
    expect(allows(["matches.read"], "members.manage")).toBe(false);
    expect(allows(["members.manage"], "members.manage")).toBe(true);
  });

  it("never offers the owner's role, nor one stronger than the member's own", () => {
    const names = (mine: typeof OWNER) => assignableRoles(ROLES, mine).map((r) => r.name);
    expect(names(OWNER)).toEqual(["coach", "player", "viewer"]);
    expect(names(COACH)).toEqual(["coach", "player", "viewer"]);
    expect(names(PLAYER)).toEqual(["player", "viewer"]);
    expect(defaultInviteRole(assignableRoles(ROLES, OWNER))?.name).toBe("player");
    expect(defaultInviteRole([VIEWER])?.name).toBe("viewer");
  });

  it("lists the teams of `/me`, none from an API that predates them", () => {
    expect(teamsOf({})).toEqual([]);
    const personal = {
      id: "1",
      kind: "personal" as const,
      name: "me",
      slug: "u-1",
      role: "owner",
      permissions: ["*"],
    };
    const team = { ...personal, id: "2", kind: "team" as const, slug: "northwind" };
    expect(teamsOf({ workspaces: [personal, team] })).toEqual([team]);
  });

  it("builds its addresses safely", () => {
    expect(teamHref("north wind", "members")).toBe("/teams/north%20wind/members");
    expect(joinPath("a/b?c")).toBe("/join/a%2Fb%3Fc");
    expect(validTeamParam("Northwind-2")).toBe(true);
    expect(validTeamParam("../admin")).toBe(false);
  });

  it("takes the slugs the API takes", () => {
    expect(validSlug("northwind")).toBe(true);
    expect(validSlug("u-7656119")).toBe(false);
    expect(validSlug("ab")).toBe(false);
    expect(validSlug("North")).toBe(false);
  });

  it("reads the code a refusal carries, as a string or a reason", () => {
    expect(refusalCode({ ok: false, status: 409, detail: "slug_taken" })).toBe("slug_taken");
    expect(refusalCode({ ok: false, status: 409, detail: { reason: "last_owner" } })).toBe(
      "last_owner",
    );
    expect(refusalCode({ ok: false, status: 409, detail: "already invited or a user" })).toBeNull();
    expect(refusalCode({ ok: false, status: 422, detail: { field: "name" } })).toBeNull();
  });
});
