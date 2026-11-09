// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Whether the API refused the address itself: FastAPI answers 422 when a path parameter cannot be
 * read, such as a session id that is not a UUID. No page lives there, so it is a 404 for the
 * player, not a server error. A 422 on anything else (a query, a body) stays an error.
 */
export function refusedAddress(status: number, body: unknown): boolean {
  if (status !== 422 || typeof body !== "object" || body === null) return false;
  const detail = (body as { detail?: unknown }).detail;
  return (
    Array.isArray(detail) &&
    detail.length > 0 &&
    detail.every(
      (error) =>
        typeof error === "object" &&
        error !== null &&
        Array.isArray((error as { loc?: unknown }).loc) &&
        (error as { loc: unknown[] }).loc[0] === "path",
    )
  );
}
