// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";
import type { LazyStart } from "./lazy-popup";
import { useCurrentSpace } from "./space";
import type { SpaceMenuProps } from "./space-menu";
import { SPACE_TRIGGER_CLASS, SpaceBadge, type SpaceLink, SpaceTriggerFace } from "./space-trigger";

/** The workspace menu itself, loaded by `SpaceMenu` on first use. */
export function SpaceMenuPopup({
  spaces,
  title,
  defaultOpen,
  focusTrigger,
}: SpaceMenuProps & LazyStart) {
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (focusTrigger) trigger.current?.focus();
  }, [focusTrigger]);
  const current = useCurrentSpace(spaces);
  if (!current) return null;
  return (
    <DropdownMenu defaultOpen={defaultOpen}>
      <DropdownMenuTrigger ref={trigger} aria-label={current.label} className={SPACE_TRIGGER_CLASS}>
        <SpaceTriggerFace space={current} />
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="start" sideOffset={6} className="w-72">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{title}</DropdownMenuLabel>
          {spaces.map((space) => (
            <SpaceItem key={space.key} space={space} current={space.key === current.key} />
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SpaceItem({ space, current }: { space: SpaceLink; current: boolean }) {
  return (
    <DropdownMenuItem
      render={<Link href={space.href} aria-current={current ? "true" : undefined} />}
      className="gap-2.5 py-1.5 aria-[current=true]:bg-muted"
    >
      <SpaceBadge space={space} className="size-6 text-[0.625rem]" />
      <span className={cn("min-w-0 flex-1 truncate", current && "font-semibold")}>
        {space.menuName}
      </span>
      {space.role && <span className="shrink-0 text-xs text-muted-foreground">{space.role}</span>}
      <Check
        aria-hidden="true"
        className={current ? "shrink-0 text-highlight" : "invisible shrink-0"}
      />
    </DropdownMenuItem>
  );
}
