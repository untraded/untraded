// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useSyncExternalStore } from "react";
import {
  getHelpOpen,
  getInstallState,
  getServerHelpOpen,
  getServerInstallState,
  type InstallState,
  subscribeInstall,
} from "@/lib/install";

/** What the install controls show (`lib/install.ts`): `unknown` until hydrated. */
export function useInstallState(): InstallState {
  return useSyncExternalStore(subscribeInstall, getInstallState, getServerInstallState);
}

/** Whether a control can do something here: the browser's dialog, or the iPhone's two taps. */
export function useCanInstall(): boolean {
  const state = useInstallState();
  return state === "prompt" || state === "ios";
}

export function useHelpOpen(): boolean {
  return useSyncExternalStore(subscribeInstall, getHelpOpen, getServerHelpOpen);
}
