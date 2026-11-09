// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import english from "../messages/en.json";
import french from "../messages/fr.json";

/** Every message by its path, with the ICU arguments it takes. */
function flatten(tree: unknown, path = ""): Map<string, string[]> {
  const found = new Map<string, string[]>();
  if (typeof tree === "string") {
    const args = [...tree.matchAll(/\{(\w+)(?:,|\})/g)].map((m) => m[1] ?? "");
    found.set(path, [...new Set(args)].sort());
  } else if (tree && typeof tree === "object") {
    for (const [key, value] of Object.entries(tree)) {
      for (const [k, v] of flatten(value, path ? `${path}.${key}` : key)) found.set(k, v);
    }
  }
  return found;
}

describe("messages", () => {
  const en = flatten(english);
  const fr = flatten(french);

  it("have the same keys in both languages", () => {
    expect([...fr.keys()].sort()).toEqual([...en.keys()].sort());
  });

  it("take the same parameters in both languages", () => {
    for (const [key, args] of en) expect({ key, args: fr.get(key) }).toEqual({ key, args });
  });
});
