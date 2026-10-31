// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import type { Me } from "../src/lib/api";
import { onboardingStep } from "../src/lib/onboarding";

const consent = {
  text_version: "1",
  analysis: true,
  research_corpus: false,
  recorded_at: "2026-10-20T10:00:00Z",
};
const me: Me = {
  id: "u",
  steam_id: "76561190000000001",
  display_name: "you",
  admin: false,
  consent,
  consent_version: "1",
  source: { enabled: true, last_success_at: null, last_error: null },
  can_add_source: true,
};

describe("onboardingStep", () => {
  it("asks for the consent first: missing, withdrawn, or to an older text", () => {
    expect(onboardingStep({ ...me, consent: null })).toBe("consent");
    expect(onboardingStep({ ...me, consent: { ...consent, analysis: false } })).toBe("consent");
    expect(onboardingStep({ ...me, consent_version: "2" })).toBe("consent");
  });

  it("then the codes, or says the operator follows the player", () => {
    expect(onboardingStep({ ...me, source: null })).toBe("codes");
    expect(onboardingStep({ ...me, source: null, can_add_source: false })).toBe("operator");
  });

  it("asks nothing of the public demo, which can give nothing", () => {
    expect(onboardingStep({ ...me, demo: true, consent: null, source: null })).toBeNull();
  });

  it("has nothing left once the player is followed, even with an error to fix", () => {
    expect(onboardingStep(me)).toBeNull();
    const error = { enabled: true, last_success_at: null, last_error: "403" };
    expect(onboardingStep({ ...me, source: error })).toBeNull();
  });
});
