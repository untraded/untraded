// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { CircleCheck, OctagonX } from "lucide-react";
import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import {
  changeRole,
  handOver,
  leaveTeam,
  removeMember,
  revokeInvitation,
  setRoster,
} from "@/app/teams/actions";
import { ConfirmSubmit } from "@/components/confirm-submit";
import { InviteLinkForm } from "@/components/teams/invite-link-form";
import { roleLabel } from "@/components/teams/role-label";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { Locale } from "@/i18n/locale";
import { findTeamInvitations, getMe, getTeam, type Team, type TeamMember } from "@/lib/api";
import { cn } from "@/lib/cn";
import { day } from "@/lib/format";
import { allows, assignableRoles, defaultInviteRole, validTeamParam } from "@/lib/teams";

type Params = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ done?: string; error?: string }>;
};

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  if (!validTeamParam(slug)) return {};
  const [team, t] = await Promise.all([getTeam(slug), getTranslations("teams")]);
  return team ? { title: `${t("members")} · ${team.name}` } : {};
}

const DONE = ["role", "removed", "roster", "revoked", "owner"] as const;
const ERRORS = [
  "forbidden",
  "role_too_high",
  "last_owner",
  "not_a_member",
  "team_not_found",
  "read_only",
  "failed",
] as const;

type T = (key: string, values?: Record<string, string | number>) => string;

/**
 * A team's members and roster, its invitation links, handing it over and leaving it. Each control
 * shows only to a role allowed to use it (the API refuses the rest anyway), none in the read-only
 * demo; what cannot be undone asks first.
 */
export default async function TeamMembers({ params, searchParams }: Params) {
  const { slug } = await params;
  if (!validTeamParam(slug)) notFound();
  const [me, t, locale, query] = await Promise.all([
    getMe(),
    getTranslations("teams"),
    getLocale(),
    searchParams,
  ]);
  if (!me) redirect("/");
  const team = await getTeam(slug);
  if (!team) redirect("/");
  const demo = me.demo === true;
  const mine = team.my_role.permissions;
  const may = {
    manage: !demo && allows(mine, "members.manage"),
    roster: !demo && allows(mine, "roster.edit"),
    own: !demo && mine.includes("*"),
  };
  const invitations = may.manage ? ((await findTeamInvitations(team.slug)) ?? []) : [];
  const self = team.members.find((m) => m.steam_id === me.steam_id);
  const owners = team.members.filter((m) => m.role.permissions.includes("*"));
  const done = DONE.find((d) => d === query.done);
  const error = query.error ? (ERRORS.find((e) => e === query.error) ?? "failed") : null;
  const giveable = assignableRoles(team.roles, team.my_role);
  return (
    <>
      <h1 className="mb-5 text-2xl font-semibold break-words md:text-[1.75rem]">{t("members")}</h1>
      <div className="flex flex-col gap-4">
        {(done || error) && (
          <p
            id="notice"
            role={error ? "alert" : "status"}
            className={cn(
              "flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm",
              error ? "border-destructive/40 text-destructive" : "border-border bg-card",
            )}
          >
            {error ? (
              <OctagonX aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            ) : (
              <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-win" />
            )}
            {error ? t(`errors.${error}`) : t(`done.${done}`)}
          </p>
        )}
        {demo && (
          <p className="rounded-md border border-dashed border-border bg-card px-3.5 py-2.5 text-sm text-muted-foreground">
            {t("readOnly")}
          </p>
        )}
        <Panel
          title={t("members")}
          aside={
            <span className="tabular-nums">
              {t("membersCount", { count: team.members.length })}
            </span>
          }
          flush
        >
          <div
            aria-hidden="true"
            className="hidden xl:grid xl:grid-cols-[minmax(10rem,1fr)_12rem_17rem_6rem] gap-4 border-b border-line-soft px-3.5 py-1.5 text-xs font-medium text-muted-foreground"
          >
            <span>{t("members")}</span>
            <span>{t("role")}</span>
            <span>{t("roster")}</span>
            <span />
          </div>
          <ul>
            {team.members.map((member) => (
              <MemberRow
                key={member.user_id}
                team={team}
                member={member}
                self={member.steam_id === me.steam_id}
                may={may}
                giveable={giveable}
                locale={locale as Locale}
                t={t}
              />
            ))}
          </ul>
        </Panel>
        {may.manage && (
          <Panel title={t("invitations")} flush>
            <div className="flex flex-col gap-3 px-3.5 py-3">
              <p className="max-w-prose text-[0.8125rem] text-muted-foreground">
                {t("invitationsLead")}
              </p>
              <InviteLinkForm
                slug={team.slug}
                roles={giveable.map((r) => ({ id: r.id, label: roleLabel(t, r.name) }))}
                defaultRole={defaultInviteRole(giveable)?.id}
                labels={{
                  role: t("inviteRole"),
                  uses: t("inviteUses"),
                  usesHint: t("inviteUsesHint"),
                  create: t("createLink"),
                  ready: t("linkReady"),
                  link: t("link"),
                  copy: t("copyLink"),
                  copied: t("copied"),
                  errors: {
                    max_uses: t("errors.max_uses"),
                    forbidden: t("errors.forbidden"),
                    role_too_high: t("errors.role_too_high"),
                    read_only: t("errors.read_only"),
                    failed: t("errors.failed"),
                  },
                }}
              />
            </div>
            {invitations.length === 0 ? (
              <p className="border-t border-line-soft px-3.5 py-3 text-sm text-muted-foreground">
                {t("noInvitations")}
              </p>
            ) : (
              <ul>
                {invitations.map((invitation) => (
                  <li
                    key={invitation.id}
                    className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line-soft px-3.5 py-2.5 text-sm"
                  >
                    <span className="tabular-nums">
                      {t("invitationLine", {
                        role: roleLabel(t, invitation.role.name),
                        uses: invitation.uses,
                        max: invitation.max_uses,
                        date: day(invitation.expires_at.slice(0, 10), locale as Locale),
                      })}
                    </span>
                    <form action={revokeInvitation}>
                      <input type="hidden" name="slug" value={team.slug} />
                      <input type="hidden" name="invitation" value={invitation.id} />
                      <ConfirmSubmit
                        size="sm"
                        label={t("revoke")}
                        question={t("revokeConfirm")}
                        confirm={t("revokeYes")}
                        cancel={t("cancel")}
                      />
                    </form>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}
        {may.own && self && <HandOver team={team} self={self} t={t} />}
        {!demo && self && (
          <Panel title={t("leave")} className="mt-4 border-destructive/40">
            {may.own && owners.length <= 1 ? (
              <p className="max-w-prose text-sm text-muted-foreground">{t("lastOwner")}</p>
            ) : (
              <form action={leaveTeam} className="flex flex-col items-start gap-2.5">
                <input type="hidden" name="slug" value={team.slug} />
                <p className="max-w-prose text-sm text-muted-foreground">{t("leaveLead")}</p>
                <ConfirmSubmit
                  label={t("leave")}
                  question={t("leaveConfirm", { team: team.name })}
                  confirm={t("leaveYes")}
                  cancel={t("cancel")}
                />
              </form>
            )}
          </Panel>
        )}
      </div>
    </>
  );
}

function MemberRow({
  team,
  member,
  self,
  may,
  giveable,
  locale,
  t,
}: {
  team: Team;
  member: TeamMember;
  self: boolean;
  may: { manage: boolean; roster: boolean; own: boolean };
  giveable: Team["roles"];
  locale: Locale;
  t: T;
}) {
  const owner = member.role.permissions.includes("*");
  // Nobody changes their own role here, and only an owner touches another owner.
  const canTouch = may.manage && !self && (!owner || may.own);
  const options = giveable.some((r) => r.id === member.role.id)
    ? giveable
    : [member.role, ...giveable];
  const canChangeRole = canTouch && options.some((r) => r.id !== member.role.id);
  const caption = "mb-1 block text-xs text-muted-foreground xl:hidden";
  const segment =
    "h-7 rounded-sm px-2.5 text-[0.8125rem] text-muted-foreground hover:text-foreground aria-pressed:bg-muted aria-pressed:font-medium aria-pressed:text-foreground";
  const roleText = roleLabel(t, member.role.name);
  return (
    <li className="grid gap-x-4 gap-y-2.5 border-t border-line-soft px-3.5 py-3 text-sm first:border-t-0 sm:grid-cols-2 xl:grid-cols-[minmax(10rem,1fr)_12rem_17rem_6rem] xl:items-center">
      <div className="flex min-w-0 items-center gap-3 sm:col-span-2 xl:col-span-1">
        <span
          aria-hidden="true"
          className="grid size-8 shrink-0 place-items-center rounded-sm bg-muted text-sm font-semibold uppercase"
        >
          {member.display_name.slice(0, 1)}
        </span>
        <div className="min-w-0">
          <p className="truncate font-semibold">
            {member.display_name}
            {self && <span className="ml-1.5 font-normal text-muted-foreground">({t("you")})</span>}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("joined", { date: day(member.joined_at.slice(0, 10), locale) })}
          </p>
        </div>
      </div>
      <div className="min-w-0">
        <span className={caption}>{t("role")} </span>
        {canChangeRole ? (
          <form action={changeRole} className="flex items-center gap-1.5">
            <input type="hidden" name="slug" value={team.slug} />
            <input type="hidden" name="user_id" value={member.user_id} />
            <select
              name="role_id"
              defaultValue={member.role.id}
              aria-label={t("roleOf", { name: member.display_name })}
              className="h-7 min-w-0 flex-1 rounded-sm border border-input bg-card px-1.5 text-[0.8125rem]"
            >
              {options.map((role) => (
                <option key={role.id} value={role.id}>
                  {roleLabel(t, role.name)}
                </option>
              ))}
            </select>
            <Button type="submit" variant="outline" size="sm">
              {t("apply")}
            </Button>
          </form>
        ) : (
          <span className="inline-block rounded-sm bg-muted px-1.5 py-0.5 text-xs font-medium">
            {roleText}
          </span>
        )}
      </div>
      <div className="min-w-0">
        <span className={caption}>{t("roster")} </span>
        {may.roster ? (
          <form action={setRoster} className="inline-flex">
            <input type="hidden" name="slug" value={team.slug} />
            <input type="hidden" name="steam_id" value={member.steam_id} />
            <fieldset className="m-0 inline-flex flex-wrap rounded-md border border-border bg-card p-0.5">
              <legend className="sr-only">{t("rosterOf", { name: member.display_name })}</legend>
              {(
                [
                  ["starter", t("makeStarter")],
                  ["standin", t("makeStandin")],
                  ["off", t("offRoster")],
                ] as const
              ).map(([place, label]) => (
                <button
                  key={place}
                  type="submit"
                  name="place"
                  value={place}
                  aria-pressed={(member.roster ?? "off") === place}
                  className={segment}
                >
                  {label}
                </button>
              ))}
            </fieldset>
          </form>
        ) : (
          <span className="text-[0.8125rem] text-muted-foreground">
            {member.roster ? t(`place.${member.roster}`) : t("offRoster")}
          </span>
        )}
      </div>
      <div className="xl:justify-self-end">
        {canTouch && (
          <form action={removeMember}>
            <input type="hidden" name="slug" value={team.slug} />
            <input type="hidden" name="user_id" value={member.user_id} />
            <ConfirmSubmit
              size="sm"
              label={t("remove")}
              question={t("removeConfirm", { name: member.display_name })}
              confirm={t("removeYes")}
              cancel={t("cancel")}
            />
          </form>
        )}
      </div>
    </li>
  );
}

/** The owner hands the team over to another member, who becomes its owner. */
function HandOver({ team, self, t }: { team: Team; self: TeamMember; t: T }) {
  const others = team.members.filter((m) => m.user_id !== self.user_id);
  return (
    <Panel title={t("handOver")}>
      {others.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("handOverNobody")}</p>
      ) : (
        <form action={handOver} className="flex flex-col items-start gap-2.5">
          <input type="hidden" name="slug" value={team.slug} />
          <p className="max-w-prose text-sm text-muted-foreground">{t("handOverLead")}</p>
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("handOverTo")}
            <select
              name="user_id"
              required
              defaultValue=""
              aria-label={t("handOverTo")}
              className="h-9 min-w-48 rounded-md border border-input bg-card px-2.5 font-normal"
            >
              <option value="" disabled>
                {t("handOverPick")}
              </option>
              {others.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </label>
          <ConfirmSubmit
            label={t("handOverButton")}
            question={t("handOverConfirm")}
            confirm={t("handOverYes")}
            cancel={t("cancel")}
          />
        </form>
      )}
    </Panel>
  );
}
