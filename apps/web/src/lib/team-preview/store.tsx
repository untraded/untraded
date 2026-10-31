// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import { clearClips, deleteClip } from "./clips";
import { EXECS, LINEUPS, STRATS } from "./data";
import { EMPTY, ownAccess, readSaved, type Saved } from "./rules";
import type { Access, Exec, Level, Lineup, Matrix, Page, Role, Strat } from "./types";

const KEY = "untraded_team_preview";

type Kind = "lineups" | "execs" | "strats";

interface Store {
  /** Seen as which role: what the page shows and lets change follows it. */
  viewAs: Role;
  setViewAs: (role: Role) => void;
  matrix: Matrix;
  setLevel: (page: Page, role: Role, level: Level) => void;
  lineups: Lineup[];
  execs: Exec[];
  strats: Strat[];
  add: <K extends Kind>(kind: K, item: Saved[K][number]) => void;
  remove: (kind: Kind, id: string) => void;
  setAccess: (kind: Kind, id: string, access: Access) => void;
  reset: () => void;
  /** False until the browser's copy is read: avoids flashing the invented team alone. */
  ready: boolean;
}

const Context = createContext<Store | null>(null);

function read(): Saved {
  try {
    return readSaved(window.localStorage.getItem(KEY));
  } catch {
    return EMPTY;
  }
}

export function TeamPreviewProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Saved>(EMPTY);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setSaved(read());
    setReady(true);
  }, []);
  const update = (change: (s: Saved) => Saved) =>
    setSaved((current) => {
      const next = change(current);
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        // Private window or full storage: the change lasts until the page is left.
      }
      return next;
    });
  const withAccess = <T extends { id: string; access: Access }>(items: T[]) =>
    items.map((item) => ({ ...item, access: saved.access[item.id] ?? item.access }));

  const store: Store = {
    ready,
    viewAs: saved.viewAs,
    setViewAs: (role) => update((s) => ({ ...s, viewAs: role })),
    matrix: saved.matrix,
    setLevel: (page, role, level) =>
      update((s) => ({
        ...s,
        matrix: { ...s.matrix, [page]: { ...s.matrix[page], [role]: level } },
      })),
    // The visitor's additions first: they are what they look for.
    lineups: withAccess([...saved.lineups, ...LINEUPS]),
    execs: withAccess([...saved.execs, ...EXECS]),
    strats: withAccess([...saved.strats, ...STRATS]),
    // What one adds stays visible and editable to the role one adds it as.
    add: (kind, item) =>
      update((s) => ({
        ...s,
        [kind]: [
          { ...item, access: ownAccess(item.access, s.viewAs), local: true },
          ...(s[kind] as unknown[]),
        ],
      })),
    remove: (kind, id) => {
      const lineup = saved.lineups.find((l) => l.id === id);
      if (kind === "lineups" && lineup?.clip) void deleteClip(lineup.clip);
      update((s) => ({ ...s, [kind]: (s[kind] as { id: string }[]).filter((i) => i.id !== id) }));
    },
    setAccess: (kind, id, access) =>
      update((s) =>
        (s[kind] as { id: string }[]).some((i) => i.id === id)
          ? {
              ...s,
              [kind]: (s[kind] as { id: string }[]).map((i) =>
                i.id === id ? { ...i, access } : i,
              ),
            }
          : { ...s, access: { ...s.access, [id]: access } },
      ),
    reset: () => {
      void clearClips();
      update(() => EMPTY);
    },
  };
  return <Context.Provider value={store}>{children}</Context.Provider>;
}

export function useTeamPreview(): Store {
  const store = useContext(Context);
  if (!store) throw new Error("useTeamPreview outside TeamPreviewProvider");
  return store;
}

/** A short unique id for something added in the browser. */
export function newId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}
