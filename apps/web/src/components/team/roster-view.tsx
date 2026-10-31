// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/cn";
import { MEMBERS } from "@/lib/team-preview/data";
import { useTeamPreview } from "@/lib/team-preview/store";
import { LEVELS, type Level, type Member, PAGES, ROLES } from "@/lib/team-preview/types";
import { Chip, useRights } from "./parts";

/** The team: who plays (starters, stand-ins, roles in game), who is who, and who may do what. */
export function RosterView() {
  const t = useTranslations("team");
  const { matrix, setLevel } = useTeamPreview();
  const { canManage } = useRights("roster");
  const group = (roster: Member["roster"]) => MEMBERS.filter((m) => m.roster === roster);

  const card = (member: Member) => (
    <li
      key={member.id}
      className="flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2.5"
    >
      <span
        aria-hidden="true"
        className="grid size-9 shrink-0 place-items-center rounded-md bg-muted text-sm font-semibold"
      >
        {member.name.charAt(0)}
      </span>
      <span className="min-w-0">
        <span className="block font-semibold">{member.name}</span>
        <span className="flex flex-wrap gap-1">
          {member.inGame.map((r) => (
            <Chip key={r}>{t(`inGame.${r}`)}</Chip>
          ))}
        </span>
      </span>
    </li>
  );

  return (
    <div className="flex flex-col gap-7">
      <section aria-labelledby="roster" className="flex flex-col gap-3">
        <h2 id="roster" className="text-sm font-semibold text-muted-foreground">
          {t("roster.title")}
        </h2>
        <div className="flex flex-col gap-1.5">
          <h3 className="text-[0.8125rem] font-medium">{t("roster.starters")}</h3>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">{group("starter").map(card)}</ul>
        </div>
        <div className="flex flex-col gap-1.5">
          <h3 className="text-[0.8125rem] font-medium">{t("roster.standins")}</h3>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">{group("standin").map(card)}</ul>
          <p className="text-xs text-muted-foreground">{t("roster.standinsHint")}</p>
        </div>
      </section>

      <section aria-labelledby="members" className="flex flex-col gap-2">
        <h2 id="members" className="text-sm font-semibold text-muted-foreground">
          {t("roster.members")}
        </h2>
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">
                  {t("roster.member")}
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  {t("roster.role")}
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  {t("roster.place")}
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  {t("roster.inGameCol")}
                </th>
              </tr>
            </thead>
            <tbody>
              {MEMBERS.map((m) => (
                <tr key={m.id} className="border-t border-line-soft">
                  <th scope="row" className="px-4 py-2 text-left font-semibold">
                    {m.name}
                  </th>
                  <td className="px-3 py-2">{t(`roles.${m.role}`)}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {m.roster ? t(`roster.${m.roster}`) : t("roster.staff")}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {m.inGame.map((r) => t(`inGame.${r}`)).join(", ") || "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="matrix" className="flex flex-col gap-2">
        <h2 id="matrix" className="text-sm font-semibold text-muted-foreground">
          {t("roster.matrix")}
        </h2>
        <p className="text-[0.8125rem] text-muted-foreground">
          {canManage ? t("roster.matrixHint") : t("roster.matrixReadOnly")}
        </p>
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">
                  {t("roster.page")}
                </th>
                {ROLES.map((role) => (
                  <th key={role} scope="col" className="px-3 py-2 font-medium">
                    {t(`roles.${role}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PAGES.map((page) => (
                <tr key={page} className="border-t border-line-soft">
                  <th scope="row" className="px-4 py-2 text-left font-medium">
                    {t(`pagesNames.${page}`)}
                  </th>
                  {ROLES.map((role) => {
                    const level = matrix[page][role];
                    const fixed = role === "owner" || !canManage;
                    return (
                      <td key={role} className="px-3 py-1.5">
                        {fixed ? (
                          <span className={cn(level === "none" && "text-muted-foreground")}>
                            {t(`levels.${level}`)}
                          </span>
                        ) : (
                          <select
                            aria-label={`${t(`pagesNames.${page}`)}, ${t(`roles.${role}`)}`}
                            value={level}
                            onChange={(event) => setLevel(page, role, event.target.value as Level)}
                            className="h-8 rounded-md border border-input bg-card px-1.5 text-sm"
                          >
                            {LEVELS.map((l) => (
                              <option key={l} value={l}>
                                {t(`levels.${l}`)}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">{t("roster.levelsHint")}</p>
      </section>
    </div>
  );
}
