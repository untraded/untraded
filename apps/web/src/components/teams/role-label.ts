// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { isDefaultRole } from "@/lib/teams";

/** A role's name as shown: the four default roles translated, any other as the team named it. */
export function roleLabel(t: (key: string) => string, name: string): string {
  return isDefaultRole(name) ? t(`roles.${name}`) : name;
}
