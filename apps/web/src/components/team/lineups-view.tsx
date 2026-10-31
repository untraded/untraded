// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Plus } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useRef, useState } from "react";
import { CopyCommand } from "@/components/copy-command";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { CLIP_TYPES, MAX_CLIP_BYTES, saveClip } from "@/lib/team-preview/clips";
import { newId, useTeamPreview } from "@/lib/team-preview/store";
import {
  type Access,
  GRENADES,
  type Grenade,
  type Lineup,
  MAPS,
  type MapId,
  SITES,
  type Side,
  type Site,
  THROWS,
  type Throw,
  text,
} from "@/lib/team-preview/types";
import {
  AccessBadge,
  AccessEditor,
  Chip,
  ClipFrame,
  Field,
  Filter,
  inputClass,
  mapLabel,
  memberName,
  useRights,
} from "./parts";

const SIDES = ["T", "CT"] as const;

/** The team's lineups, by map and side, as cards with their clip; one opens its detail. */
export function LineupsView() {
  const t = useTranslations("team");
  const locale = useLocale();
  const { lineups, setAccess, remove } = useTeamPreview();
  const rights = useRights("lineups");
  // A link from an exec opens its lineup on its map: `?map=inferno&open=l-inferno-ct`.
  const query = useSearchParams();
  const asked = query.get("map");
  const [map, setMap] = useState<MapId | "all">(
    MAPS.includes(asked as MapId) ? (asked as MapId) : "all",
  );
  const [side, setSide] = useState<Side | "all">("all");
  const [grenade, setGrenade] = useState<Grenade | "all">("all");
  const [site, setSite] = useState<Site | "all">("all");
  const [open, setOpen] = useState<Lineup | null>(
    () => lineups.find((l) => l.id === query.get("open") && rights.sees(l.access)) ?? null,
  );
  const [adding, setAdding] = useState(false);
  const shown = lineups.filter(
    (l) =>
      rights.sees(l.access) &&
      (map === "all" || l.map === map) &&
      (side === "all" || l.side === side) &&
      (grenade === "all" || l.grenade === grenade) &&
      (site === "all" || l.site === site),
  );
  const current = open ? (lineups.find((l) => l.id === open.id) ?? null) : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-prose text-sm text-muted-foreground">{t("lineups.lead")}</p>
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
          label={t("grenade")}
          value={grenade}
          options={GRENADES}
          onChange={setGrenade}
          name={(g) => t(`grenades.${g}`)}
        />
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
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((lineup) => (
            <li key={lineup.id}>
              <button
                type="button"
                onClick={() => setOpen(lineup)}
                className="flex w-full cursor-pointer flex-col overflow-hidden rounded-lg border border-border bg-card text-left hover:border-foreground focus-visible:outline-2 focus-visible:outline-ring"
              >
                <ClipFrame clip={lineup.clip} label={t("lineups.clipPlaceholder")} />
                <span className="flex flex-col gap-1.5 px-3 py-2.5">
                  <span className="flex flex-wrap items-center gap-1">
                    <Chip tone={lineup.side === "CT" ? "ct" : "t"}>{lineup.side}</Chip>
                    <Chip>{t(`grenades.${lineup.grenade}`)}</Chip>
                    <Chip>{t(`sites.${lineup.site}`)}</Chip>
                    <Chip>{mapLabel(lineup.map)}</Chip>
                    {lineup.local && (
                      <span className="text-xs text-muted-foreground">{t("yours")}</span>
                    )}
                  </span>
                  <span className="font-semibold">{text(lineup.title, locale)}</span>
                  <span className="text-xs text-muted-foreground">
                    {t(`throws.${lineup.throw}`)} · {t("by", { name: memberName(lineup.author) })}
                  </span>
                  <AccessBadge access={lineup.access} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <Sheet open={current !== null} onOpenChange={(value) => !value && setOpen(null)}>
        <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-lg">
          {current && (
            <div className="flex flex-col gap-4 p-4">
              <SheetTitle className="pr-8 text-lg font-semibold">
                {text(current.title, locale)}
              </SheetTitle>
              <ClipFrame
                clip={current.clip}
                label={t("lineups.clipPlaceholder")}
                className="rounded-md"
              />
              <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
                <dt className="text-muted-foreground">{t("lineups.where")}</dt>
                <dd>
                  {mapLabel(current.map)} · {current.side} · {t(`sites.${current.site}`)} ·{" "}
                  {t(`grenades.${current.grenade}`)}
                </dd>
                <dt className="text-muted-foreground">{t("lineups.from")}</dt>
                <dd>{text(current.from, locale)}</dd>
                <dt className="text-muted-foreground">{t("lineups.aim")}</dt>
                <dd>{text(current.aim, locale)}</dd>
                <dt className="text-muted-foreground">{t("lineups.throw")}</dt>
                <dd>{t(`throws.${current.throw}`)}</dd>
                <dt className="text-muted-foreground">{t("lineups.author")}</dt>
                <dd>{memberName(current.author)}</dd>
              </dl>
              {current.setpos && (
                <div className="flex flex-col gap-1">
                  <span className="text-[0.8125rem] font-medium">{t("lineups.setpos")}</span>
                  <CopyCommand
                    command={current.setpos}
                    copy={t("copy", { command: current.setpos })}
                  />
                  <span className="text-xs text-muted-foreground">{t("lineups.setposHint")}</span>
                </div>
              )}
              <div className="rounded-md border border-border p-3">
                <AccessEditor
                  value={current.access}
                  disabled={!rights.edits(current.access)}
                  onChange={(access) => setAccess("lineups", current.id, access)}
                />
                {!rights.edits(current.access) && (
                  <p className="mt-2 text-xs text-muted-foreground">{t("access.readOnly")}</p>
                )}
              </div>
              {current.local && rights.edits(current.access) && (
                <Button
                  variant="outline"
                  onClick={() => {
                    remove("lineups", current.id);
                    setOpen(null);
                  }}
                  className="self-start"
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
            <SheetTitle className="text-lg font-semibold">{t("lineups.new")}</SheetTitle>
            <AddLineup
              defaultMap={map === "all" ? "mirage" : map}
              onDone={(added) => {
                setAdding(false);
                // Show what was just added, whatever map the filters were on.
                if (added) {
                  setMap(added);
                  setSide("all");
                  setGrenade("all");
                  setSite("all");
                }
              }}
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

function AddLineup({
  defaultMap,
  onDone,
}: {
  defaultMap: MapId;
  /** With the map of the lineup added, or nothing when cancelled. */
  onDone: (added?: MapId) => void;
}) {
  const t = useTranslations("team");
  const { add } = useTeamPreview();
  const [access, setAccessValue] = useState<Access>({ view: ["coach", "player"], edit: ["coach"] });
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  function pick(chosen: File | undefined) {
    setProblem(null);
    if (!chosen) return setFile(null);
    if (!CLIP_TYPES.includes(chosen.type)) return setProblem(t("lineups.clipType"));
    if (chosen.size > MAX_CLIP_BYTES) return setProblem(t("lineups.clipTooBig"));
    setFile(chosen);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) ?? "").trim();
    setBusy(true);
    const id = newId("l");
    let clip: string | null = null;
    if (file) {
      try {
        await saveClip(id, file);
        clip = id;
      } catch {
        // The form stays open: the visitor saves without the clip, or tries another file.
        setFile(null);
        if (fileInput.current) fileInput.current.value = "";
        setProblem(t("lineups.clipFailed"));
        setBusy(false);
        return;
      }
    }
    add("lineups", {
      id,
      map: value("map") as MapId,
      side: value("side") as Side,
      site: value("site") as Site,
      grenade: value("grenade") as Grenade,
      title: value("title"),
      from: value("from"),
      aim: value("aim"),
      throw: value("throw") as Throw,
      setpos: value("setpos"),
      clip,
      author: "ayla",
      access,
    });
    setBusy(false);
    onDone(value("map") as MapId);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <Field label={t("lineups.name")}>
        <input name="title" required maxLength={80} className={inputClass} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
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
        <Field label={t("grenade")}>
          <select name="grenade" className={inputClass}>
            {GRENADES.map((g) => (
              <option key={g} value={g}>
                {t(`grenades.${g}`)}
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
      </div>
      <Field label={t("lineups.from")}>
        <input name="from" maxLength={120} className={inputClass} />
      </Field>
      <Field label={t("lineups.aim")}>
        <input name="aim" maxLength={120} className={inputClass} />
      </Field>
      <Field label={t("lineups.throw")}>
        <select name="throw" className={inputClass}>
          {THROWS.map((th) => (
            <option key={th} value={th}>
              {t(`throws.${th}`)}
            </option>
          ))}
        </select>
      </Field>
      <Field label={t("lineups.setpos")} hint={t("lineups.setposHint")}>
        <input
          name="setpos"
          maxLength={160}
          placeholder="setpos 0 0 0; setang 0 0 0"
          className={`${inputClass} font-mono text-[0.8125rem]`}
        />
      </Field>
      <Field label={t("lineups.clip")} hint={t("lineups.clipHint")}>
        <input
          ref={fileInput}
          type="file"
          accept="video/mp4,video/webm"
          onChange={(event) => pick(event.target.files?.[0])}
          className="text-sm file:mr-3 file:h-8 file:cursor-pointer file:rounded-md file:border file:border-border file:bg-card file:px-3 file:text-sm"
        />
      </Field>
      {problem && (
        <p role="alert" className="text-sm text-loss">
          {problem}
        </p>
      )}
      <div className="rounded-md border border-border p-3">
        <AccessEditor value={access} onChange={setAccessValue} />
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={() => onDone()}>
          {t("cancel")}
        </Button>
        <Button type="submit" disabled={busy}>
          {t("save")}
        </Button>
      </div>
    </form>
  );
}
