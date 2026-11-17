// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { RAIL_CLIP, RAIL_MOTION, RAIL_TOOLTIP } from "./nav";

/** A workspace the switch lists: the player's own, or one of their teams. */
export interface SpaceLink {
  /** `~personal`, or the team's slug. */
  key: string;
  /** On the switch: the team's name, or the player's. */
  name: string;
  /** In the menu: the team's name, or "My space". */
  menuName: string;
  /** In the badge: the team's initials, or the player's initial. */
  badge: string;
  team: boolean;
  /** Under the name: "Team · owner", or "My space". */
  line: string;
  /** In the menu, at the right of a team: the player's role in it. */
  role: string | null;
  href: string;
  /** The switch's accessible name while this space is open: "Switch workspace: Northwind". */
  label: string;
}

/** The square badge of a space: a team's initials on the accent's soft tint, the player's initial
 * on the muted ground. */
export function SpaceBadge({ space, className }: { space: SpaceLink; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid shrink-0 place-items-center rounded-sm font-bold uppercase",
        space.team ? "bg-highlight-soft text-highlight" : "bg-muted text-foreground",
        className,
      )}
    >
      {space.badge}
    </span>
  );
}

/**
 * The switch at the head of the rail, shared by the stand-in and the real menu trigger so that
 * swapping one for the other changes nothing on screen. Folded: the badge alone, the name in a
 * tooltip; unfolded: the badge, the name and its line, the chevrons, in a framed button that
 * leaves room for the rail's toggle; on a touch screen's folded rail: the badge with the name
 * under it, small.
 */
export const SPACE_TRIGGER_CLASS = cn(
  "group/nav relative flex h-8 w-full shrink-0 items-center rounded-md border border-transparent px-1.5 text-left text-chrome-foreground transition-[height,width,border-color,background-color] hover:bg-muted aria-expanded:bg-muted",
  "md:group-data-[collapsed=false]/shell:h-11 md:group-data-[collapsed=false]/shell:w-[calc(100%-34px)] md:group-data-[collapsed=false]/shell:border-chrome-line",
  "touch-rail:h-auto touch-rail:flex-col touch-rail:justify-center touch-rail:gap-1 touch-rail:px-0 touch-rail:py-1",
  RAIL_MOTION,
);

export function SpaceTriggerFace({ space }: { space: SpaceLink }) {
  return (
    <>
      <SpaceBadge space={space} className="size-7 text-[0.6875rem]" />
      {/* The button's own label names it: what follows is for the eye. */}
      <span aria-hidden="true" className={cn(RAIL_CLIP, "flex items-center touch-rail:hidden")}>
        <span className="min-w-0 flex-1 pl-2.5">
          <span className="block truncate text-sm leading-tight font-semibold">{space.name}</span>
          <span className="block truncate text-xs leading-tight text-chrome-muted">
            {space.line}
          </span>
        </span>
        <ChevronsUpDown className="ml-1 size-4 shrink-0 text-chrome-muted" />
      </span>
      <span
        aria-hidden="true"
        className="hidden w-full truncate px-0.5 text-center text-[0.6875rem] leading-tight touch-rail:block"
      >
        {space.name}
      </span>
      <span aria-hidden="true" className={RAIL_TOOLTIP}>
        {space.name}
      </span>
    </>
  );
}

/** The phone's top bar: the same switch, always with its name. 44 px high, a finger's target. */
export const SPACE_BAR_CLASS =
  "flex h-11 max-w-full min-w-0 items-center gap-2 rounded-lg border border-chrome-line pr-2.5 pl-1.5 text-left text-sm font-semibold text-chrome-foreground hover:bg-muted aria-expanded:bg-muted";

export function SpaceBarFace({ space }: { space: SpaceLink }) {
  return (
    <>
      <SpaceBadge space={space} className="size-[26px] text-[0.6875rem]" />
      <span aria-hidden="true" className="min-w-0 truncate">
        {space.name}
      </span>
      <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-chrome-muted" />
    </>
  );
}
