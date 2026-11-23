// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Installing the site as an app (a PWA). Chrome and Edge (Android, desktop) fire
 * `beforeinstallprompt` when the site can be installed: the event is kept, and an "Install the
 * app" control replays it. Safari on iPhone and iPad has no such event: the control explains the
 * two taps instead. Nothing is offered once the app is installed (it runs standalone), nor where
 * the browser cannot install it (Firefox on a desktop).
 *
 * The pure functions below decide; the store at the bottom holds the browser's side.
 */

/** What the install controls show: nothing until the browser is known (`unknown`, on the server
 * and before hydration), nothing when `installed` or `unavailable`. */
export type InstallState = "unknown" | "installed" | "prompt" | "ios" | "unavailable";

export interface InstallFacts {
  /** The page runs as the installed app (`display-mode: standalone`, or Safari's flag). */
  standalone: boolean;
  /** The browser offered to install (a kept `beforeinstallprompt`). */
  promptable: boolean;
  /** An iPhone or iPad, where only the Share menu installs. */
  ios: boolean;
}

export function installState(facts: InstallFacts): InstallState {
  if (facts.standalone) return "installed";
  if (facts.promptable) return "prompt";
  if (facts.ios) return "ios";
  return "unavailable";
}

/** An iPhone or iPad. iPadOS reports itself as a Mac, told apart by its touch screen. */
export function isIos(userAgent: string, platform: string, maxTouchPoints: number): boolean {
  return /iPad|iPhone|iPod/.test(userAgent) || (platform === "MacIntel" && maxTouchPoints > 1);
}

/**
 * What the phone's install strip remembers, in this browser: on how many different days the
 * player opened the site, the last of them, and whether the strip was closed for good.
 */
export interface StripMemory {
  days: number;
  last: string | null;
  dismissed: boolean;
}

export const NO_MEMORY: StripMemory = { days: 0, last: null, dismissed: false };

/** The strip waits for the player to come back: from the third day they open the site. */
export const STRIP_FROM_DAY = 3;

/** Today's visit counted (once per calendar day, `today` as YYYY-MM-DD). */
export function countVisit(memory: StripMemory, today: string): StripMemory {
  return memory.last === today ? memory : { ...memory, days: memory.days + 1, last: today };
}

/** Whether the strip shows: the browser can install (or explain how), the player came back on
 * enough days, and never closed it. */
export function showsStrip(state: InstallState, memory: StripMemory): boolean {
  return (
    (state === "prompt" || state === "ios") && memory.days >= STRIP_FROM_DAY && !memory.dismissed
  );
}

/** The memory read back from storage: anything malformed counts as nothing. */
export function parseMemory(raw: string | null): StripMemory {
  if (!raw) return NO_MEMORY;
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null) return NO_MEMORY;
    const { days, last, dismissed } = value as Record<string, unknown>;
    return {
      days: typeof days === "number" && Number.isFinite(days) && days >= 0 ? Math.floor(days) : 0,
      last: typeof last === "string" && /^\d{4}-\d{2}-\d{2}$/.test(last) ? last : null,
      dismissed: dismissed === true,
    };
  } catch {
    return NO_MEMORY;
  }
}

/** The local calendar day, YYYY-MM-DD. */
export function localDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

// --- The browser's side -------------------------------------------------------------------------

/** Chrome's event, not in the DOM types. */
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const STORAGE_KEY = "untraded_install";

/** A menu's or a sheet's closing animation (200 ms), and a little more. */
const CLOSE_MS = 250;

/** The installed app, in any of the display modes a manifest can ask for. */
const STANDALONE =
  "(display-mode: standalone), (display-mode: minimal-ui), (display-mode: fullscreen), (display-mode: window-controls-overlay)";

let deferred: BeforeInstallPromptEvent | null = null;
let claimed = false;
let installedNow = false;
let helpOpen = false;
let snapshot: InstallState = "unknown";
const listeners = new Set<() => void>();

function compute(): InstallState {
  return installState({
    standalone:
      installedNow ||
      window.matchMedia(STANDALONE).matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true,
    promptable: deferred !== null,
    ios: isIos(navigator.userAgent, navigator.platform, navigator.maxTouchPoints),
  });
}

function emit() {
  snapshot = compute();
  for (const listener of listeners) listener();
}

// Listened to as soon as this module loads (it is part of the root layout's code), so that an
// event fired before React hydrates is not missed.
if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    // Where our own controls offer it (the signed-in shell), no mini-infobar from the browser on
    // top of them; elsewhere (a visitor's sign-in page) the browser's own offer stays.
    if (claimed) event.preventDefault();
    deferred = event as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    installedNow = true;
    helpOpen = false;
    emit();
  });
  window.matchMedia(STANDALONE).addEventListener("change", emit);
  snapshot = compute();
}

/** Called by the shell's install controls, as their code loads: from then on they offer the
 * install, not the browser. */
export function claimInstallOffer() {
  claimed = true;
}

export function subscribeInstall(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getInstallState(): InstallState {
  return snapshot;
}

export function getServerInstallState(): InstallState {
  return "unknown";
}

/** Whether the iPhone help is open (one help for every control, hosted by the shell). */
export function getHelpOpen(): boolean {
  return helpOpen;
}

export function getServerHelpOpen(): boolean {
  return false;
}

export function setHelpOpen(open: boolean) {
  if (helpOpen === open) return;
  helpOpen = open;
  for (const listener of listeners) listener();
}

/**
 * What an "Install the app" control does: the browser's own install dialog, or on an iPhone the
 * two taps. Resolves once the dialog is answered. The browser's event serves once: it is dropped,
 * and the controls hide until the browser offers again.
 *
 * `afterClose`: the control sits in a menu or a sheet that closes on the click; the help then
 * opens once it has closed and handed the focus back, so that the help keeps it. (The browser's
 * dialog, though, must open within the click.)
 */
export async function install({
  afterClose = false,
}: {
  afterClose?: boolean;
} = {}): Promise<void> {
  if (deferred) {
    const event = deferred;
    deferred = null;
    emit();
    try {
      await event.prompt();
      await event.userChoice;
    } catch {
      // Already used, or refused by the browser: nothing to tell the player.
    }
    return;
  }
  if (snapshot !== "ios") return;
  if (afterClose) window.setTimeout(() => setHelpOpen(true), CLOSE_MS);
  else setHelpOpen(true);
}

export function readStripMemory(): StripMemory {
  try {
    return parseMemory(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return NO_MEMORY;
  }
}

export function writeStripMemory(memory: StripMemory) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
  } catch {
    // Storage blocked (a private window): the strip may come back, nothing worse.
  }
}
