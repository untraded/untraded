// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { apiSend, findTeam, getMe, refusalCode, refusedField } from "@/lib/api";
import { joinPath, teamHref, validToken } from "@/lib/teams";

// The team's writes, as `docs/contrat-api-equipes.md` (HQ) names them. Every input is checked
// here before it reaches an API path; the API checks the permissions. A refusal comes back in the
// page's address as its code (`?error=last_owner`), never with anything else.

const SLUG = /^[a-z0-9-]{3,32}$/i;
const UUID = /^[0-9a-f-]{36}$/i;
const STEAM_ID = /^\d{17}$/;

/** The codes a team page knows how to say; anything else reads as `failed`. */
const KNOWN = new Set([
  "forbidden",
  "role_too_high",
  "last_owner",
  "not_a_member",
  "team_not_found",
  "read_only",
  "max_uses",
]);

/** Codes the API sends under another name than the site's message: the demo's refusal (403
 * `demo`) and the database's check of an invitation's uses. */
const ALIASES: Record<string, string> = { demo: "read_only", max_uses_invalid: "max_uses" };

function field(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "").trim();
}

function slugOf(formData: FormData): string | null {
  const slug = field(formData, "slug");
  return SLUG.test(slug) ? slug.toLowerCase() : null;
}

/** Back to the members page, with what happened. */
function back(slug: string, outcome: { done: string } | { error: string }): never {
  const members = teamHref(slug, "members");
  revalidatePath(members);
  revalidatePath(teamHref(slug));
  const query = "done" in outcome ? `done=${outcome.done}` : `error=${outcome.error}`;
  redirect(`${members}?${query}#notice`);
}

function errorOf(result: Awaited<ReturnType<typeof apiSend>>): string {
  const raw = refusalCode(result);
  const code = raw ? (ALIASES[raw] ?? raw) : null;
  if (code && KNOWN.has(code)) return code;
  return result.status === 403 ? "forbidden" : "failed";
}

/** Gives a member another role. */
export async function changeRole(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const user = field(formData, "user_id");
  const role = field(formData, "role_id");
  if (!slug || !UUID.test(user) || !UUID.test(role)) return;
  const result = await apiSend(`/teams/${slug}/members/${encodeURIComponent(user)}`, "PATCH", {
    role_id: role,
  });
  back(slug, result.ok ? { done: "role" } : { error: errorOf(result) });
}

/** Removes a member from the team. */
export async function removeMember(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const user = field(formData, "user_id");
  if (!slug || !UUID.test(user)) return;
  const result = await apiSend(`/teams/${slug}/members/${encodeURIComponent(user)}`, "DELETE");
  back(slug, result.ok ? { done: "removed" } : { error: errorOf(result) });
}

/** Leaves the team: the player removes themself (read here, never from the form), then lands
 * on their own space. */
export async function leaveTeam(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  if (!slug) return;
  const [me, team] = await Promise.all([getMe(), findTeam(slug)]);
  const self = me && team?.members.find((m) => m.steam_id === me.steam_id);
  if (!self) back(slug, { error: "failed" });
  const result = await apiSend(
    `/teams/${slug}/members/${encodeURIComponent(self.user_id)}`,
    "DELETE",
  );
  if (!result.ok) back(slug, { error: errorOf(result) });
  revalidatePath("/", "layout");
  redirect("/");
}

/** Hands the team over to another member, who becomes its owner. */
export async function handOver(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const user = field(formData, "user_id");
  if (!slug || !UUID.test(user)) return;
  const result = await apiSend(`/teams/${slug}/owner`, "POST", { user_id: user });
  if (result.ok) revalidatePath("/", "layout");
  back(slug, result.ok ? { done: "owner" } : { error: errorOf(result) });
}

/** Puts a member on the roster (`starter` or `standin`), or takes them off it (`off`). */
export async function setRoster(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const steamId = field(formData, "steam_id");
  const place = field(formData, "place");
  if (!slug || !STEAM_ID.test(steamId) || !["starter", "standin", "off"].includes(place)) return;
  const path = `/teams/${slug}/roster/${steamId}`;
  const result =
    place === "off" ? await apiSend(path, "DELETE") : await apiSend(path, "PUT", { role: place });
  back(slug, result.ok ? { done: "roster" } : { error: errorOf(result) });
}

/** Revokes an invitation link: it stops working at once. */
export async function revokeInvitation(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const id = field(formData, "invitation");
  if (!slug || !UUID.test(id)) return;
  const result = await apiSend(`/teams/${slug}/invitations/${encodeURIComponent(id)}`, "DELETE");
  back(slug, result.ok ? { done: "revoked" } : { error: errorOf(result) });
}

export type InviteLinkState = {
  /** The link's path on this site (`/join/<token>`), shown once: the API never gives it again. */
  path: string | null;
  error: string | null;
};

/** Creates an invitation link. Its token comes back in the form's state only, never in an
 * address or a log. */
export async function createInvitation(
  _: InviteLinkState,
  formData: FormData,
): Promise<InviteLinkState> {
  const slug = slugOf(formData);
  const role = field(formData, "role_id");
  const uses = Number(field(formData, "max_uses"));
  if (!slug || !UUID.test(role)) return { path: null, error: "failed" };
  if (!Number.isInteger(uses) || uses < 1 || uses > 20) return { path: null, error: "max_uses" };
  const result = await apiSend(`/teams/${slug}/invitations`, "POST", {
    role_id: role,
    max_uses: uses,
  });
  if (!result.ok) {
    return {
      path: null,
      error: refusedField(result) === "max_uses" ? "max_uses" : errorOf(result),
    };
  }
  const token = (result.data as { token?: unknown } | null)?.token;
  revalidatePath(teamHref(slug, "members"));
  return typeof token === "string" && token
    ? { path: joinPath(token), error: null }
    : { path: null, error: "failed" };
}

/** Shares the player's solo matches with a team, or stops. */
export async function setShareSolo(formData: FormData): Promise<void> {
  const slug = slugOf(formData);
  const share = field(formData, "share");
  if (!slug || !["on", "off"].includes(share)) return;
  const result = await apiSend(`/teams/${slug}/share-solo`, "PUT", { share: share === "on" });
  revalidatePath("/settings");
  redirect(result.ok ? "/settings#teams" : "/settings?share=failed#teams");
}

/** Joins the team an invitation link leads to, on the player's explicit click. */
export async function acceptInvitation(formData: FormData): Promise<void> {
  const token = field(formData, "token");
  if (!validToken(token)) return;
  const result = await apiSend(`/team-invitations/${encodeURIComponent(token)}/accept`, "POST");
  const here = joinPath(token);
  if (!result.ok) {
    const code = refusalCode(result);
    const error =
      code === "invitation_invalid" || code === "already_member" || code === "consent_required"
        ? code
        : code === "demo"
          ? "read_only"
          : "failed";
    redirect(`${here}?error=${error}`);
  }
  revalidatePath("/", "layout");
  const slug = (result.data as { slug?: unknown } | null)?.slug;
  redirect(typeof slug === "string" && SLUG.test(slug) ? teamHref(slug) : "/");
}
