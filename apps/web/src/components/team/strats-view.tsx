// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { MEMBERS } from "@/lib/team-preview/data";
import { newId, useTeamPreview } from "@/lib/team-preview/store";
import {
  type Access,
  MAPS,
  type MapId,
  type Side,
  STRAT_KINDS,
  type Strat,
  type StratKind,
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

const SIDES = ["T", "CT"] as const;
const PLAYERS = MEMBERS.filter((m) => m.roster !== null);

/** The stratbook: by map and kind (default, pistol, eco...), each strat with its steps per player,
 * its notes and its tags. */
export function StratsView() {
  const t = useTranslations("team");
  const locale = useLocale();
  const { strats, setAccess, remove } = useTeamPreview();
  const rights = useRights("strats");
  const [map, setMap] = useState<MapId | "all">("all");
  const [kind, setKind] = useState<StratKind | "all">("all");
  const [side, setSide] = useState<Side | "all">("all");
  const [editing, setEditing] = useState<Strat | null>(null);
  const [adding, setAdding] = useState(false);
  const shown = strats.filter(
    (s) =>
      rights.sees(s.access) &&
      (map === "all" || s.map === map) &&
      (kind === "all" || s.kind === kind) &&
      (side === "all" || s.side === side),
  );
  const current = editing ? (strats.find((s) => s.id === editing.id) ?? null) : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-prose text-sm text-muted-foreground">{t("strats.lead")}</p>
        <Button onClick={() => setAdding(true)} disabled={!rights.canAdd} className="gap-1.5">
          <Plus aria-hidden="true" />
          {t("add")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <Filter label={t("map")} value={map} options={MAPS} onChange={setMap} name={mapLabel} />
        <Filter
          masculine
          label={t("side")}
          value={side}
          options={SIDES}
          onChange={setSide}
          name={(s) => s}
        />
        <Filter
          masculine
          label={t("kind")}
          value={kind}
          options={STRAT_KINDS}
          onChange={setKind}
          name={(k) => t(`strats.kinds.${k}`)}
        />
      </div>
      {shown.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {shown.map((strat) => (
            <li
              key={strat.id}
              className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4"
            >
              <div className="flex flex-col gap-1">
                <span className="flex flex-wrap items-center gap-1">
                  <Chip>{mapLabel(strat.map)}</Chip>
                  <Chip tone={strat.side === "CT" ? "ct" : "t"}>{strat.side}</Chip>
                  <Chip>{t(`strats.kinds.${strat.kind}`)}</Chip>
                  {strat.local && (
                    <span className="text-xs text-muted-foreground">{t("yours")}</span>
                  )}
                </span>
                <h2 className="font-semibold">{text(strat.title, locale)}</h2>
              </div>
              <ul className="flex flex-col">
                {strat.steps.map((step, i) => (
                  <li
                    // biome-ignore lint/suspicious/noArrayIndexKey: one player can have two steps
                    key={i}
                    className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-2 border-t border-line-soft py-1.5 text-sm first:border-t-0"
                  >
                    <span className="font-semibold">{memberName(step.member)}</span>
                    <span>{text(step.text, locale)}</span>
                  </li>
                ))}
              </ul>
              {text(strat.notes, locale) && (
                <p className="rounded-md bg-muted px-3 py-2 text-sm">
                  <span className="block text-xs font-medium text-muted-foreground">
                    {t("strats.notes")}
                  </span>
                  {text(strat.notes, locale)}
                </p>
              )}
              <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line-soft pt-2.5">
                <span className="flex flex-wrap items-center gap-2">
                  {[...new Set(strat.tags)].map((tag) => (
                    <span key={tag} className="text-xs text-muted-foreground">
                      #{tag}
                    </span>
                  ))}
                  <AccessBadge access={strat.access} />
                </span>
                <Button variant="outline" size="sm" onClick={() => setEditing(strat)}>
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
                onChange={(access) => setAccess("strats", current.id, access)}
              />
              {!rights.edits(current.access) && (
                <p className="text-xs text-muted-foreground">{t("access.readOnly")}</p>
              )}
              {current.local && rights.edits(current.access) && (
                <Button
                  variant="outline"
                  className="self-start"
                  onClick={() => {
                    remove("strats", current.id);
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
            <SheetTitle className="text-lg font-semibold">{t("strats.new")}</SheetTitle>
            <AddStrat defaultMap={map === "all" ? "mirage" : map} onDone={() => setAdding(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function AddStrat({ defaultMap, onDone }: { defaultMap: MapId; onDone: () => void }) {
  const t = useTranslations("team");
  const { add } = useTeamPreview();
  const [access, setAccessValue] = useState<Access>({ view: ["coach", "player"], edit: ["coach"] });
  const starters = PLAYERS.filter((m) => m.roster === "starter");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) ?? "").trim();
    add("strats", {
      id: newId("s"),
      map: value("map") as MapId,
      side: value("side") as Side,
      kind: value("kind") as StratKind,
      title: value("title"),
      steps: starters
        .map((_, i) => ({ member: value(`member-${i}`), text: value(`step-${i}`) }))
        .filter((step) => step.text !== ""),
      notes: value("notes"),
      tags: value("tags")
        .split(",")
        .map((tag) => tag.trim())
        .filter((tag, i, all) => tag !== "" && all.indexOf(tag) === i),
      access,
    });
    onDone();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Field label={t("strats.name")}>
        <input name="title" required maxLength={80} className={inputClass} />
      </Field>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label={t("map")}>
          <select name="map" defaultValue={defaultMap} className={inputClass}>
            {MAPS.map((m) => (
              <option key={m} value={m}>
                {mapLabel(m)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("side")}>
          <select name="side" className={inputClass}>
            {SIDES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field label={t("kind")}>
          <select name="kind" className={inputClass}>
            {STRAT_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`strats.kinds.${k}`)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[0.8125rem] font-medium">{t("strats.steps")}</legend>
        {starters.map((member, i) => (
          <div key={member.id} className="grid grid-cols-[6rem_minmax(0,1fr)] gap-2">
            <select
              name={`member-${i}`}
              defaultValue={member.id}
              aria-label={t("execs.playerN", { n: i + 1 })}
              className={inputClass}
            >
              {PLAYERS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <input
              name={`step-${i}`}
              aria-label={t("strats.stepN", { n: i + 1 })}
              placeholder={t("strats.step")}
              className={inputClass}
            />
          </div>
        ))}
      </fieldset>
      <Field label={t("strats.notes")}>
        <textarea name="notes" className={areaClass} />
      </Field>
      <Field label={t("strats.tags")} hint={t("strats.tagsHint")}>
        <input name="tags" maxLength={80} className={inputClass} />
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
