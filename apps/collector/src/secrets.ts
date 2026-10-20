// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// Secrets stored in the database (`ingest_source.secret`, e.g. a player's match history
// authentication code) are encrypted by the application, never stored in clear (ADR 0011).
//
// Format, shared with the other services: version byte 1, 12-byte random nonce, AES-256-GCM
// ciphertext, 16-byte tag. The key is UNTRADED_SECRET_KEY: 32 bytes, base64. The source id is
// the additional authenticated data, so a secret copied onto another row does not decrypt.

import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

const VERSION = 1;
const NONCE_BYTES = 12;
const TAG_BYTES = 16;

export function secretKey(base64: string | undefined): Buffer {
  if (!base64) throw new Error("missing UNTRADED_SECRET_KEY (32 bytes, base64)");
  const key = Buffer.from(base64, "base64");
  if (key.length !== 32) {
    throw new Error(`UNTRADED_SECRET_KEY must be 32 bytes once decoded, got ${key.length}`);
  }
  return key;
}

export function encrypt(key: Buffer, plaintext: string, aad: string): Buffer {
  const nonce = randomBytes(NONCE_BYTES);
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  cipher.setAAD(Buffer.from(aad, "utf8"));
  const body = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  return Buffer.concat([Buffer.from([VERSION]), nonce, body, cipher.getAuthTag()]);
}

export function decrypt(key: Buffer, sealed: Buffer, aad: string): string {
  if (sealed.length < 1 + NONCE_BYTES + TAG_BYTES || sealed[0] !== VERSION) {
    throw new Error("unknown secret format");
  }
  const nonce = sealed.subarray(1, 1 + NONCE_BYTES);
  const tag = sealed.subarray(sealed.length - TAG_BYTES);
  const decipher = createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAAD(Buffer.from(aad, "utf8"));
  decipher.setAuthTag(tag);
  const body = sealed.subarray(1 + NONCE_BYTES, sealed.length - TAG_BYTES);
  return Buffer.concat([decipher.update(body), decipher.final()]).toString("utf8");
}
