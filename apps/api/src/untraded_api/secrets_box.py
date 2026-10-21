# SPDX-FileCopyrightText: 2026 The Untraded Authors
# SPDX-License-Identifier: AGPL-3.0-only
"""Secrets stored in the database (`ingest_source.secret`), in the format the collector reads
(`apps/collector/src/secrets.ts`): version byte 1, 12-byte random nonce, AES-256-GCM ciphertext
and its 16-byte tag. The key is UNTRADED_SECRET_KEY (32 bytes, base64); the source id is the
additional authenticated data, so a secret copied onto another row does not decrypt."""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = 1
NONCE_BYTES = 12


def secret_key(encoded: str | None) -> bytes:
    if not encoded:
        raise ValueError("missing UNTRADED_SECRET_KEY (32 bytes, base64)")
    # As lenient as the collector's Node decoder, which reads the same variable: the padding
    # may be missing (`openssl rand -base64 32 | tr -d =`), and URL-safe letters are accepted.
    text = encoded.strip().replace("-", "+").replace("_", "/")
    text += "=" * (-len(text) % 4)
    try:
        key = base64.b64decode(text, validate=True)
    except binascii.Error as error:
        raise ValueError("UNTRADED_SECRET_KEY is not base64") from error
    if len(key) != 32:
        raise ValueError(f"UNTRADED_SECRET_KEY must be 32 bytes once decoded, got {len(key)}")
    return key


def encrypt(key: bytes, plaintext: str, aad: str) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
    return bytes([VERSION]) + nonce + sealed


def decrypt(key: bytes, sealed: bytes, aad: str) -> str:
    if len(sealed) < 1 + NONCE_BYTES + 16 or sealed[0] != VERSION:
        raise ValueError("unknown secret format")
    nonce, body = sealed[1 : 1 + NONCE_BYTES], sealed[1 + NONCE_BYTES :]
    return AESGCM(key).decrypt(nonce, body, aad.encode("utf-8")).decode("utf-8")
