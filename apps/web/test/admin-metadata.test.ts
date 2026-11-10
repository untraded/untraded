// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminOnlyMetadata } from "@/lib/admin-metadata";
import { getMe, type Me } from "@/lib/api";

vi.mock("@/lib/api", () => ({ getMe: vi.fn() }));

const me = vi.mocked(getMe);

describe("adminOnlyMetadata", () => {
  const title = vi.fn(async () => "Players");

  beforeEach(() => {
    me.mockReset();
    title.mockClear();
  });

  it("names the page for an admin", async () => {
    me.mockResolvedValue({ admin: true } as Me);
    expect(await adminOnlyMetadata(title)).toEqual({ title: "Players" });
  });

  it("gives a player no title of its own, as the 404 of any address", async () => {
    me.mockResolvedValue({ admin: false } as Me);
    expect(await adminOnlyMetadata(title)).toEqual({});
    expect(title).not.toHaveBeenCalled();
  });

  it("gives a signed-out visitor no title of its own", async () => {
    me.mockResolvedValue(null);
    expect(await adminOnlyMetadata(title)).toEqual({});
    expect(title).not.toHaveBeenCalled();
  });
});
