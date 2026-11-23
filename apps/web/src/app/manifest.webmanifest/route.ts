// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import type { MetadataRoute } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { CHROME_DARK } from "@/lib/theme-color";

/**
 * The web app manifest (`/manifest.webmanifest`), so that the site installs as an app. Every
 * address in it is relative to the site: an instance under another address installs the same.
 * The icons are the logo's (`public/icons/`, a trademark: a fork replaces them, see
 * `docs/self-hosting.md`); the maskable one keeps the sign in the central safe zone. The splash
 * screen and the title bar take the dark chrome's colour.
 *
 * In the browser's language (browsers fetch a manifest without cookies, so the settings' choice
 * does not reach it). A route of our own rather than `app/manifest.ts`, so that the answer says it
 * varies with the language: a caching proxy in front of an instance must not serve one language
 * to everyone.
 */
// It reads the request (the language): never prerendered.
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return new Response(JSON.stringify(await manifest()), {
    headers: {
      "Content-Type": "application/manifest+json; charset=utf-8",
      "Cache-Control": "private, no-cache",
      Vary: "Cookie, Accept-Language",
    },
  });
}

async function manifest(): Promise<MetadataRoute.Manifest> {
  const [locale, t, nav] = await Promise.all([
    getLocale(),
    getTranslations("install"),
    getTranslations("nav"),
  ]);
  return {
    id: "/",
    name: "Untraded",
    short_name: "Untraded",
    description: t("manifestDescription"),
    lang: locale,
    dir: "ltr",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: CHROME_DARK,
    theme_color: CHROME_DARK,
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: nav("home"), url: "/", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      {
        name: nav("matches"),
        url: "/matches",
        icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }],
      },
    ],
  };
}
