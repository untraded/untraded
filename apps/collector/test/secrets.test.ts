// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { randomBytes } from "node:crypto";
import { describe, expect, it } from "vitest";
import { decrypt, encrypt, secretKey } from "../src/secrets.js";

const key = randomBytes(32);

describe("secrets", () => {
  it("round-trips, with a fresh nonce each time", () => {
    const a = encrypt(key, "ABCD-12345-EFGH", "source-1");
    const b = encrypt(key, "ABCD-12345-EFGH", "source-1");
    expect(a.equals(b)).toBe(false);
    expect(a[0]).toBe(1);
    expect(decrypt(key, a, "source-1")).toBe("ABCD-12345-EFGH");
  });

  it("refuses another row, another key or a tampered secret", () => {
    const sealed = encrypt(key, "code", "source-1");
    expect(() => decrypt(key, sealed, "source-2")).toThrow();
    expect(() => decrypt(randomBytes(32), sealed, "source-1")).toThrow();
    const tampered = Buffer.from(sealed);
    tampered[14] = (tampered[14] ?? 0) ^ 1;
    expect(() => decrypt(key, tampered, "source-1")).toThrow();
    expect(() => decrypt(key, Buffer.from([2, 0, 0]), "source-1")).toThrow(/format/);
  });

  it("checks the key", () => {
    expect(secretKey(key.toString("base64")).equals(key)).toBe(true);
    expect(() => secretKey(undefined)).toThrow(/missing/);
    expect(() => secretKey(randomBytes(16).toString("base64"))).toThrow(/32 bytes/);
  });
});
