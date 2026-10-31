// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Clapperboard, Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useId, useState } from "react";
import { cn } from "@/lib/cn";
import { loadClip } from "@/lib/team-preview/clips";
import { MEMBERS } from "@/lib/team-preview/data";
import { canEdit, canSee } from "@/lib/team-preview/rules";
import { useTeamPreview } from "@/lib/team-preview/store";
import { type Access, allows, type Page, ROLES, type Role } from "@/lib/team-preview/types";

/** A map's display name: `dust2` → `Dust2`. */
export const mapLabel = (map: string) => map.charAt(0).toUpperCase() + map.slice(1);

export const memberName = (id: string) => MEMBERS.find((m) => m.id === id)?.name ?? id;

/** What the role the page is seen with may do here: see the page, add to it, change an item. */
export function useRights(page: Page) {
  const { viewAs, matrix } = useTeamPreview();
  const level = matrix[page][viewAs];
  return {
    role: viewAs,
    canAdd: allows(level, "edit"),
    canManage: allows(level, "manage"),
    sees: (access: Access) => canSee(level, access, viewAs),
    edits: (access: Access) => canEdit(level, access, viewAs),
  };
}

/** A row of select filters; `all` keeps everything. */
export function Filter<T extends string>({
  label,
  value,
  options,
  onChange,
  name,
  masculine,
}: {
  /** The word for everything agrees with the filter's noun in French (side, site). */
  masculine?: boolean;
  label: string;
  value: T | "all";
  options: readonly T[];
  onChange: (value: T | "all") => void;
  name: (option: T) => string;
}) {
  const t = useTranslations("team");
  return (
    <label className="flex items-center gap-1.5 text-[0.8125rem]">
      <span className="text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T | "all")}
        className="h-8 rounded-md border border-input bg-card px-2 text-sm"
      >
        <option value="all">{t(masculine ? "allMasculine" : "all")}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {name(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Who sees an item and who changes it, by role; the owner always does both. */
export function AccessEditor({
  value,
  onChange,
  disabled,
}: {
  value: Access;
  onChange: (access: Access) => void;
  disabled?: boolean;
}) {
  const t = useTranslations("team");
  const id = useId();
  const toggle = (what: keyof Access, role: Role, on: boolean) => {
    const next = {
      ...value,
      [what]: on ? [...value[what], role] : value[what].filter((r) => r !== role),
    };
    // Changing an item means seeing it.
    if (what === "edit" && on && !next.view.includes(role)) next.view = [...next.view, role];
    if (what === "view" && !on) next.edit = next.edit.filter((r) => r !== role);
    onChange(next);
  };
  return (
    <fieldset disabled={disabled} className="flex flex-col gap-2 text-[0.8125rem]">
      <legend className="mb-1 font-medium">{t("access.title")}</legend>
      {(["view", "edit"] as const).map((what) => (
        <div key={what} className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="w-24 text-muted-foreground">{t(`access.${what}`)}</span>
          {ROLES.filter((r) => r !== "owner").map((role) => (
            <label
              key={role}
              htmlFor={`${id}-${what}-${role}`}
              className="inline-flex items-center gap-1.5"
            >
              <input
                id={`${id}-${what}-${role}`}
                type="checkbox"
                checked={value[what].includes(role)}
                onChange={(event) => toggle(what, role, event.target.checked)}
                className="size-3.5 accent-[var(--highlight)]"
              />
              {t(`roles.${role}`)}
            </label>
          ))}
        </div>
      ))}
      <p className="text-xs text-muted-foreground">{t("access.ownerAlways")}</p>
    </fieldset>
  );
}

/** Who sees an item, in a few words, for its card. */
export function AccessBadge({ access }: { access: Access }) {
  const t = useTranslations("team");
  const roles = ["owner", ...access.view] as Role[];
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Lock aria-hidden="true" className="size-3" />
      <span className="sr-only">{t("access.view")} </span>
      {roles.map((r) => t(`roles.${r}`)).join(", ")}
    </span>
  );
}

/**
 * A lineup's clip: the video the visitor sent (kept in their browser), looped and muted, else a
 * neutral frame. The invented lineups have no clip: none is taken from anyone.
 */
export function ClipFrame({
  clip,
  label,
  className,
}: {
  clip: string | null;
  label: string;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!clip) return;
    let live = true;
    let made: string | null = null;
    loadClip(clip)
      .then((blob) => {
        if (!live || !blob) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [clip]);
  return (
    <div className={cn("relative aspect-video overflow-hidden bg-muted", className)}>
      {url ? (
        <video
          src={url}
          autoPlay
          loop
          muted
          playsInline
          className="size-full object-cover"
          aria-label={label}
        />
      ) : (
        <div className="grid size-full place-items-center text-muted-foreground">
          <span className="flex flex-col items-center gap-1.5 text-xs">
            <Clapperboard aria-hidden="true" className="size-6" />
            {label}
          </span>
        </div>
      )}
    </div>
  );
}

/** A labelled form field. */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    // The control is the child: the label wraps it, so it names it.
    // biome-ignore lint/a11y/noLabelWithoutControl: the input, select or textarea is in children
    <label className="flex flex-col gap-1 text-[0.8125rem]">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

export const inputClass = "h-9 rounded-md border border-input bg-card px-2.5 text-sm";
export const areaClass = "min-h-20 rounded-md border border-input bg-card px-2.5 py-2 text-sm";

/** A small chip: a side, a site, a grenade. */
export function Chip({ children, tone }: { children: ReactNode; tone?: "ct" | "t" }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-[3px] border border-border px-1.5 text-[0.6875rem] font-semibold",
        tone === "ct" && "border-side-ct/60 text-side-ct",
        tone === "t" && "border-side-t/60 text-side-t",
      )}
    >
      {children}
    </span>
  );
}
