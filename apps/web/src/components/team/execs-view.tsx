// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Plus, Timer } from "lucide-react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { MEMBERS } from "@/lib/team-preview/data";
import { newId, useTeamPreview } from "@/lib/team-preview/store";
import {
  type Access,
  type Exec,
  MAPS,
  type MapId,
  SITES,
  type Site,
  text,
} from "@/lib/team-preview/types";
import {
  AccessBadge,
  AccessEditor,
  areaClass,
  Chip,
  Field,
  Filter,
  inputClass,
  mapLabel,
  memberName,
  useRights,
} from "./parts";

const PLAYERS = MEMBERS.filter((m) => m.roster !== null);

/** The team's executes, by map and site: who does what, which grenades, when, in which order. */
export function ExecsView() {
  const t = useTranslations("team");
  const locale = useLocale();
  const { execs, lineups, setAccess, remove } = useTeamPreview();
  const rights = useRights("execs");
  const [map, setMap] = useState<MapId | "all">("all");
  const [site, setSite] = useState<Site | "all">("all");
  const [editing, setEditing] = useState<Exec | null>(null);
  const [adding, setAdding] = useState(false);
  const shown = execs.filter(
    (e) =>
      rights.sees(e.access) &&
      (map === "all" || e.map === map) &&
      (site === "all" || e.site === site),
  );
  const current = editing ? (execs.find((e) => e.id === editing.id) ?? null) : null;
  const lineupName = (id: string) => {
    const found = lineups.find((l) => l.id === id);
    return found ? text(found.title, locale) : null;
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-prose text-sm text-muted-foreground">{t("execs.lead")}</p>
        <Button onClick={() => setAdding(true)} disabled={!rights.canAdd} className="gap-1.5">
          <Plus aria-hidden="true" />
          {t("add")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <Filter label={t("map")} value={map} options={MAPS} onChange={setMap} name={mapLabel} />
        <Filter
          masculine
          label={t("site")}
          value={site}
          options={SITES}
          onChange={setSite}
          name={(s) => t(`sites.${s}`)}
        />
      </div>
      {shown.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {shown.map((exec) => (
            <li
              key={exec.id}
              className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex flex-col gap-1">
                  <span className="flex flex-wrap items-center gap-1">
                    <Chip>{mapLabel(exec.map)}</Chip>
                    <Chip>{t(`sites.${exec.site}`)}</Chip>
                    {exec.local && (
                      <span className="text-xs text-muted-foreground">{t("yours")}</span>
                    )}
                  </span>
                  <h2 className="font-semibold">{text(exec.title, locale)}</h2>
                </div>
                <span className="inline-flex items-center gap-1 font-mono text-sm">
                  <Timer aria-hidden="true" className="size-4 text-muted-foreground" />
                  <span className="sr-only">{t("execs.timing")} </span>
                  {exec.timing}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <h3 className="text-xs font-medium text-muted-foreground">{t("execs.tasks")}</h3>
                <ul className="flex flex-col">
                  {exec.tasks.map((task) => (
                    <li
                      key={task.member}
                      className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-2 border-t border-line-soft py-1.5 text-sm first:border-t-0"
                    >
                      <span className="font-semibold">{memberName(task.member)}</span>
                      <span>
                        {text(task.task, locale)}
                        {task.lineup && lineupName(task.lineup) && (
                          <Link
                            href="/team/lineups"
                            className="ml-1.5 text-xs text-link underline underline-offset-3"
                          >
                            {lineupName(task.lineup)}
                          </Link>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              {exec.steps.length > 0 && (
                <div className="flex flex-col gap-1">
                  <h3 className="text-xs font-medium text-muted-foreground">{t("execs.steps")}</h3>
                  <ol className="flex list-decimal flex-col gap-1 pl-5 text-sm">
                    {exec.steps.map((step) => (
                      <li key={text(step, "en")}>{text(step, locale)}</li>
                    ))}
                  </ol>
                </div>
              )}
              <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line-soft pt-2.5">
                <AccessBadge access={exec.access} />
                <Button variant="outline" size="sm" onClick={() => setEditing(exec)}>
                  {t("access.title")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Sheet open={current !== null} onOpenChange={(value) => !value && setEditing(null)}>
        <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-md">
          {current && (
            <div className="flex flex-col gap-4 p-4">
              <SheetTitle className="pr-8 text-lg font-semibold">
                {text(current.title, locale)}
              </SheetTitle>
              <AccessEditor
                value={current.access}
                disabled={!rights.edits(current.access)}
                onChange={(access) => setAccess("execs", current.id, access)}
              />
              {!rights.edits(current.access) && (
                <p className="text-xs text-muted-foreground">{t("access.readOnly")}</p>
              )}
              {current.local && rights.edits(current.access) && (
                <Button
                  variant="outline"
                  className="self-start"
                  onClick={() => {
                    remove("execs", current.id);
                    setEditing(null);
                  }}
                >
                  {t("remove")}
                </Button>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Sheet open={adding} onOpenChange={setAdding}>
        <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
          <div className="flex flex-col gap-4 p-4">
            <SheetTitle className="text-lg font-semibold">{t("execs.new")}</SheetTitle>
            <AddExec defaultMap={map === "all" ? "mirage" : map} onDone={() => setAdding(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function AddExec({ defaultMap, onDone }: { defaultMap: MapId; onDone: () => void }) {
  const t = useTranslations("team");
  const locale = useLocale();
  const { add, lineups } = useTeamPreview();
  const [map, setMap] = useState<MapId>(defaultMap);
  const [access, setAccessValue] = useState<Access>({ view: ["coach", "player"], edit: ["coach"] });
  const starters = PLAYERS.filter((m) => m.roster === "starter");
  const options = lineups.filter((l) => l.map === map);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) ?? "").trim();
    add("execs", {
      id: newId("e"),
      map,
      site: value("site") as Site,
      title: value("title"),
      timing: value("timing"),
      tasks: starters
        .map((_, i) => ({
          member: value(`member-${i}`),
          task: value(`task-${i}`),
          lineup: value(`lineup-${i}`) || undefined,
        }))
        .filter((task) => task.task !== ""),
      steps: value("steps")
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      access,
    });
    onDone();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Field label={t("execs.name")}>
        <input name="title" required maxLength={80} className={inputClass} />
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label={t("map")}>
          <select
            value={map}
            onChange={(event) => setMap(event.target.value as MapId)}
            className={inputClass}
          >
            {MAPS.map((m) => (
              <option key={m} value={m}>
                {mapLabel(m)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("site")}>
          <select name="site" className={inputClass}>
            {SITES.map((s) => (
              <option key={s} value={s}>
                {t(`sites.${s}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("execs.timing")}>
          <input
            name="timing"
            placeholder="1:10"
            maxLength={5}
            className={`${inputClass} font-mono`}
          />
        </Field>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[0.8125rem] font-medium">{t("execs.tasks")}</legend>
        {starters.map((member, i) => (
          <div
            key={member.id}
            className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2 sm:grid-cols-[6rem_minmax(0,1fr)_10rem]"
          >
            <select
              name={`member-${i}`}
              defaultValue={member.id}
              aria-label={t("execs.player")}
              className={inputClass}
            >
              {PLAYERS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <input
              name={`task-${i}`}
              aria-label={t("execs.task")}
              placeholder={t("execs.task")}
              className={inputClass}
            />
            <select
              name={`lineup-${i}`}
              aria-label={t("execs.lineup")}
              className={`${inputClass} col-span-2 sm:col-span-1`}
            >
              <option value="">{t("execs.noLineup")}</option>
              {options.map((l) => (
                <option key={l.id} value={l.id}>
                  {text(l.title, locale)}
                </option>
              ))}
            </select>
          </div>
        ))}
      </fieldset>
      <Field label={t("execs.steps")} hint={t("execs.stepsHint")}>
        <textarea name="steps" className={areaClass} />
      </Field>
      <div className="rounded-md border border-border p-3">
        <AccessEditor value={access} onChange={setAccessValue} />
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          {t("cancel")}
        </Button>
        <Button type="submit">{t("save")}</Button>
      </div>
    </form>
  );
}
