// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

// Spike S0.3: when the user downloads a FACEIT demo, send its signed URL to a local Untraded server.
// The extension never calls FACEIT itself: the user clicks "Watch demo" on the match page and
// passes FACEIT's own checks; the extension only sees the download the browser then starts.

const api = globalThis.browser ?? globalThis.chrome;
const SERVER = "http://127.0.0.1:8765/ingest/url";
const DEMO_HOSTS = [".backblazeb2.com", ".faceit-cdn.net"];
const DEMO_PATH = /^\/cs2\/([\w-]+)\.dem\.(zst|gz)$/;

function faceitDemo(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  if (!DEMO_HOSTS.some((host) => parsed.hostname.endsWith(host))) return null;
  const match = parsed.pathname.match(DEMO_PATH);
  return match ? { file: match[1] } : null;
}

function setBadge(text, color) {
  api.action.setBadgeText({ text });
  api.action.setBadgeBackgroundColor({ color });
}

api.downloads.onCreated.addListener(async (item) => {
  const url = item.finalUrl || item.url;
  const demo = faceitDemo(url);
  if (!demo) return;
  try {
    const response = await fetch(SERVER, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: "faceit", url, file: demo.file, seen_at: Date.now() / 1000 }),
    });
    setBadge(response.ok ? "OK" : String(response.status), response.ok ? "#2e7d32" : "#c62828");
  } catch (error) {
    console.error("Untraded: local server unreachable", error);
    setBadge("ERR", "#c62828");
  }
});
