// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { createHash } from "node:crypto";
import en from "../../messages/en.json";
import fr from "../../messages/fr.json";
import { logoHorizontalSvg } from "../components/brand/logo";
import { LOCALE_COOKIE, THEME_COOKIE } from "../i18n/locale";

/**
 * The page the service worker shows when a page cannot load for want of a network
 * (`app/offline/route.ts`). It is kept in the browser's cache, so it holds nothing personal: the
 * same file for every visitor, in both languages, built from the messages. A few lines of script
 * pick the player's language and theme from their cookies (else the browser's), and reload the
 * page once the network is back.
 *
 * Self-contained, in the "Instrument" direction: the dark top bar with the logo, one panel with a
 * title band. Its colours are the site's (`globals.css`); its type falls back on the system's
 * when IBM Plex is not installed (the site's own font files are not cached).
 */

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function block(lang: "en" | "fr", messages: typeof en) {
  const t = messages.offline;
  return `<div class="l" lang="${lang}" data-l="${lang}">
<div class="panel" role="region" aria-labelledby="h-${lang}">
<div class="head"><h1 id="h-${lang}">${escapeHtml(t.heading)}</h1></div>
<div class="body"><p>${escapeHtml(t.body)}</p>
<button type="button" class="retry">${escapeHtml(t.retry)}</button></div>
</div>
</div>`;
}

const STYLE = `
:root{color-scheme:light dark;
--bg:light-dark(#edf0f3,#161819);--fg:light-dark(#111821,#eeeeee);--card:light-dark(#ffffff,#1f2224);
--head:light-dark(#f3f5f8,#24282a);--muted:light-dark(#536072,#a4a9ab);--border:light-dark(#d6dce3,#2e3336);
--primary:light-dark(#d4a72c,#d9b44a);--primary-hover:light-dark(#c39a22,#e5c466);--primary-fg:light-dark(#111821,#1b1d1e);--ring:light-dark(#9a7400,#e3c46a);
--chrome:#1b1f24;--chrome-fg:#e9eaea;--chrome-line:#2c3238}
:root[data-theme=light]{color-scheme:light}
:root[data-theme=dark]{color-scheme:dark;--chrome:#101213;--chrome-fg:#eeeeee;--chrome-line:#24282a}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--chrome:#101213;--chrome-fg:#eeeeee;--chrome-line:#24282a}}
*{box-sizing:border-box}
body{margin:0;min-height:100dvh;background:var(--bg);color:var(--fg);
font:15px/1.5 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;align-items:center;gap:10px;min-height:calc(52px + env(safe-area-inset-top));padding:env(safe-area-inset-top) 16px 0;
background:var(--chrome);color:var(--chrome-fg);border-bottom:1px solid var(--chrome-line)}
header .logo{height:20px;width:auto}
main{max-width:34rem;margin:0 auto;padding:32px 16px}
.panel{background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden}
.head{background:var(--head);border-bottom:1px solid var(--border);padding:8px 14px}
h1{margin:0;font-size:.9375rem;font-weight:600}
.body{padding:14px}
p{margin:0 0 14px;color:var(--muted)}
.retry{font:inherit;font-size:.875rem;font-weight:500;height:36px;padding:0 14px;border:0;border-radius:4px;
background:var(--primary);color:var(--primary-fg);cursor:pointer;touch-action:manipulation}
.retry:hover{background:var(--primary-hover)}
.retry:focus-visible{outline:3px solid var(--ring);outline-offset:2px}
html:not([data-lang=fr]) [data-l=fr],html[data-lang=fr] [data-l=en]{display:none}
`;

// A reload when the network comes back, or on the button, wired first; then the language and the
// theme from the site's cookies (not HttpOnly: the settings write them), else the browser's. The
// cookies are compared with fixed values, never decoded nor inserted into the page.
const SCRIPT = `(function(){
function go(){location.reload()}
window.addEventListener("online",go);
document.querySelectorAll(".retry").forEach(function(b){b.addEventListener("click",go)});
var c={};document.cookie.split(";").forEach(function(p){var i=p.indexOf("=");if(i>0)c[p.slice(0,i).trim()]=p.slice(i+1).trim()});
var l=c[${JSON.stringify(LOCALE_COOKIE)}];
if(l!=="fr"&&l!=="en"){l="en";var w=navigator.languages||[navigator.language||""];for(var j=0;j<w.length;j++){var x=String(w[j]).toLowerCase().split("-")[0];if(x==="fr"||x==="en"){l=x;break}}}
var r=document.documentElement;r.setAttribute("data-lang",l);r.lang=l;document.title=r.getAttribute("data-title-"+l);
var t=c[${JSON.stringify(THEME_COOKIE)}];if(t==="light"||t==="dark")r.setAttribute("data-theme",t);
})();`;

export function offlineHtml(): string {
  return `<!doctype html>
<html lang="en" data-title-en="${escapeHtml(`${en.offline.title} · Untraded`)}" data-title-fr="${escapeHtml(`${fr.offline.title} · Untraded`)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#1b1f24" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#101213" media="(prefers-color-scheme: dark)">
<title>${escapeHtml(`${en.offline.title} · Untraded`)}</title>
<style>${STYLE}</style>
</head>
<body>
<header>${logoHorizontalSvg("logo")}</header>
<main>
${block("en", en)}
${block("fr", fr)}
</main>
<script>${SCRIPT}</script>
</body>
</html>
`;
}

/** A short fingerprint of the page: the service worker names its cache after it, so that a new
 * offline page (new words, new colours) comes with a new worker, which replaces the old copy. */
export function offlineVersion(): string {
  return createHash("sha256").update(offlineHtml()).digest("hex").slice(0, 12);
}
