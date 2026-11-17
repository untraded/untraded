// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** A form's hidden fields, one per entry: the ids an action needs to know what it acts on. */
export function HiddenFields({ values }: { values: Record<string, string | number> }) {
  return (
    <>
      {Object.entries(values).map(([name, value]) => (
        <input key={name} type="hidden" name={name} value={value} />
      ))}
    </>
  );
}
