// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** A module fetched once, on demand: `load()` starts it (or returns the load under way) and
 * `current` holds it once it is there. A failed load is forgotten, so the next call tries again. */
export interface LazyModule<T> {
  load(): Promise<T>;
  readonly current: T | undefined;
}

export function lazyModule<T>(fetch: () => Promise<T>): LazyModule<T> {
  let pending: Promise<T> | undefined;
  let current: T | undefined;
  return {
    load() {
      pending ??= fetch().then(
        (value) => {
          current = value;
          return value;
        },
        (error: unknown) => {
          pending = undefined;
          throw error;
        },
      );
      return pending;
    },
    get current() {
      return current;
    },
  };
}
