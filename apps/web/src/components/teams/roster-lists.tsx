// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { Team, TeamMember } from "@/lib/api";
import { roleLabel } from "./role-label";

/** The roster, read only: starters, then stand-ins, each with their role. */
export async function RosterLists({ team, meSteamId }: { team: Team; meSteamId: string }) {
  const t = await getTranslations("teams");
  const groups = [
    { key: "starters", members: team.members.filter((m) => m.roster === "starter") },
    { key: "standins", members: team.members.filter((m) => m.roster === "standin") },
  ] as const;
  if (groups.every((g) => g.members.length === 0)) {
    return <p className="px-3.5 py-3 text-sm text-muted-foreground">{t("rosterEmpty")}</p>;
  }
  return (
    <>
      <p className="border-b border-line-soft px-3.5 py-2 text-xs text-muted-foreground">
        {t("rosterLead")}
      </p>
      {groups.map(
        (group) =>
          group.members.length > 0 && (
            <section key={group.key} aria-labelledby={`roster-${group.key}`}>
              <h3
                id={`roster-${group.key}`}
                className="flex items-baseline gap-2 px-3.5 pt-3 pb-1 text-xs font-semibold text-muted-foreground"
              >
                {t(group.key)}
                <span className="font-normal tabular-nums">{group.members.length}</span>
              </h3>
              <ul className="pb-2">
                {group.members.map((m) => (
                  <MemberLine key={m.user_id} member={m} self={m.steam_id === meSteamId} t={t} />
                ))}
              </ul>
            </section>
          ),
      )}
    </>
  );
}

function MemberLine({
  member,
  self,
  t,
}: {
  member: TeamMember;
  self: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  return (
    <li className="flex items-center gap-3 px-3.5 py-1.5 text-sm">
      <span
        aria-hidden="true"
        className="grid size-7 shrink-0 place-items-center rounded-sm bg-muted text-xs font-semibold uppercase"
      >
        {member.display_name.slice(0, 1)}
      </span>
      <span className="min-w-0 truncate font-medium">
        {member.display_name}
        {self && <span className="ml-1.5 font-normal text-muted-foreground">({t("you")})</span>}
      </span>
      <span className="ml-auto shrink-0 text-xs text-muted-foreground">
        {roleLabel(t, member.role.name)}
      </span>
    </li>
  );
}
