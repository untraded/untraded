// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it, vi } from "vitest";
import { lazyModule } from "../src/lib/lazy";

describe("lazyModule", () => {
  it("fetches only on demand, and only once", async () => {
    const fetch = vi.fn(async () => "menu");
    const lazy = lazyModule(fetch);
    expect(fetch).not.toHaveBeenCalled();
    expect(lazy.current).toBeUndefined();
    const [a, b] = await Promise.all([lazy.load(), lazy.load()]);
    expect([a, b]).toEqual(["menu", "menu"]);
    expect(await lazy.load()).toBe("menu");
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(lazy.current).toBe("menu");
  });

  it("tries again after a failed load", async () => {
    const fetch = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce("sheet");
    const lazy = lazyModule(fetch);
    await expect(lazy.load()).rejects.toThrow("offline");
    expect(lazy.current).toBeUndefined();
    expect(await lazy.load()).toBe("sheet");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
