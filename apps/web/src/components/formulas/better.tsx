// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** Which way is better, with an arrow that is never the only sign. */
export function Better({ better, label }: { better: string; label: string }) {
  const arrow = better === "higher" ? "▲" : better === "lower" ? "▼" : "";
  return (
    <span className="whitespace-nowrap">
      {arrow && <span aria-hidden="true">{arrow} </span>}
      {label}
    </span>
  );
}
