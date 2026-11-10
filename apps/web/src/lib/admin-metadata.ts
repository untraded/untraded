// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { Metadata } from "next";
import { getMe } from "@/lib/api";

/**
 * The metadata of a page for admins only: its title for an admin. Anyone else gets the 404, so
 * nothing of its own here: the tab keeps the site's title, as for any address that leads
 * nowhere, and does not name the page. `/me` is read once per request (`apiGet` is cached), the
 * same answer the page's own guard reads; the title is only translated for an admin.
 */
export async function adminOnlyMetadata(title: () => Promise<string>): Promise<Metadata> {
  const me = await getMe();
  return me?.admin ? { title: await title() } : {};
}
