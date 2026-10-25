// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { sectionOf } from "../src/components/shell/nav";
import { pickTheme } from "../src/i18n/locale";

describe("shell", () => {
  it("marks the section a page belongs to", () => {
    expect(sectionOf("/")).toBe("home");
    expect(sectionOf("/sessions")).toBe("sessions");
    expect(sectionOf("/sessions/0000")).toBe("sessions");
    expect(sectionOf("/matches/0000")).toBe("matches");
    expect(sectionOf("/settings")).toBe("settings");
    expect(sectionOf("/formulas/base.adr")).toBe("formulas");
    expect(sectionOf("/admin")).toBe("admin");
    expect(sectionOf("/admin/health")).toBe("admin");
    expect(sectionOf("/report")).toBeNull();
    expect(sectionOf("/sessionsx")).toBeNull();
  });

  it("follows the system unless the player chose a theme", () => {
    expect(pickTheme(undefined)).toBe("system");
    expect(pickTheme("dark")).toBe("dark");
    expect(pickTheme("light")).toBe("light");
    expect(pickTheme("purple")).toBe("system");
  });
});
