// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The preview's rules, pure (tested): who sees and who edits what, and reading back what the
// browser kept, whatever state it is in.

import { MATRIX } from "./data";
import {
  type Access,
  allows,
  type Exec,
  LEVELS,
  type Level,
  type Lineup,
  type Matrix,
  may,
  PAGES,
  ROLES,
  type Role,
  type Strat,
} from "./types";

/** What a visitor changed, kept in their browser only. */
export interface Saved {
  version: 1;
  viewAs: Role;
  matrix: Matrix;
  lineups: Lineup[];
  execs: Exec[];
  strats: Strat[];
  /** The access a visitor set on an invented item, by id. */
  access: Record<string, Access>;
}

export const EMPTY: Saved = {
  version: 1,
  viewAs: "owner",
  matrix: MATRIX,
  lineups: [],
  execs: [],
  strats: [],
  access: {},
};

/** Whether a role sees an item: the page must be open to it, and the item too. */
export function canSee(level: Level, access: Access, role: Role): boolean {
  return allows(level, "view") && may(access, role, "view");
}

/** Whether a role may change an item: it edits the page, and the item lets it. */
export function canEdit(level: Level, access: Access, role: Role): boolean {
  return allows(level, "edit") && may(access, role, "edit");
}

/** An item's access with its author's role in both lists: what one adds never hides from them. */
export function ownAccess(access: Access, role: Role): Access {
  if (role === "owner") return access;
  return {
    view: access.view.includes(role) ? access.view : [...access.view, role],
    edit: access.edit.includes(role) ? access.edit : [...access.edit, role],
  };
}

const isRole = (value: unknown): value is Role => ROLES.includes(value as Role);
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function readAccess(value: unknown): Access | null {
  if (!isRecord(value) || !Array.isArray(value.view) || !Array.isArray(value.edit)) return null;
  return { view: value.view.filter(isRole), edit: value.edit.filter(isRole) };
}

/** The items of a kept list that still have the shape of one (an id, an access). */
function readItems<T extends { id: string; access: Access }>(value: unknown): T[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isRecord(item) || typeof item.id !== "string") return [];
    const access = readAccess(item.access);
    return access ? [{ ...(item as unknown as T), access, local: true }] : [];
  });
}

/** The permission matrix, rebuilt on the invented one page by page and role by role. */
function readMatrix(value: unknown): Matrix {
  const kept = isRecord(value) ? value : {};
  const matrix = {} as Matrix;
  for (const page of PAGES) {
    const row = isRecord(kept[page]) ? kept[page] : {};
    matrix[page] = {} as Matrix[typeof page];
    for (const role of ROLES) {
      const level = row[role];
      matrix[page][role] =
        role === "owner"
          ? "manage"
          : LEVELS.includes(level as Level)
            ? (level as Level)
            : MATRIX[page][role];
    }
  }
  return matrix;
}

/** What the browser kept, read back field by field: anything missing or broken falls back on the
 * invented team, never breaks the pages. */
export function readSaved(raw: string | null): Saved {
  if (!raw) return EMPTY;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return EMPTY;
  }
  if (!isRecord(parsed) || parsed.version !== 1) return EMPTY;
  const access: Record<string, Access> = {};
  if (isRecord(parsed.access)) {
    for (const [id, value] of Object.entries(parsed.access)) {
      const read = readAccess(value);
      if (read) access[id] = read;
    }
  }
  return {
    version: 1,
    viewAs: isRole(parsed.viewAs) ? parsed.viewAs : "owner",
    matrix: readMatrix(parsed.matrix),
    lineups: readItems<Lineup>(parsed.lineups),
    execs: readItems<Exec>(parsed.execs),
    strats: readItems<Strat>(parsed.strats),
    access,
  };
}
