// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// What an invited player still has to give before the collector follows their matches.

import type { Me } from "./api";

/**
 * - `consent`: no consent yet, a consent to an older text, or a withdrawn one;
 * - `codes`: consented, but no codes yet, and this server can keep them;
 * - `operator`: consented, but this server cannot keep codes (the operator follows them);
 * - `null`: nothing left to give.
 */
export type OnboardingStep = "consent" | "codes" | "operator" | null;

export function onboardingStep(me: Me): OnboardingStep {
  const { consent } = me;
  if (!consent?.analysis || consent.text_version !== me.consent_version) {
    return "consent";
  }
  if (me.source === null) return me.can_add_source ? "codes" : "operator";
  return null;
}
