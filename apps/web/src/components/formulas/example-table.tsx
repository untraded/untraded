// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

/** A cell that reads as a number: digits with a sign, separators, a decimal mark or a percent
 * (`\s` takes the narrow and no-break spaces of French numbers too). */
const NUMBER = /^[-−+]?[\d\s.,]*\d[\d\s.,]*%?$/;

/**
 * The table of a formula's example, head row first, as the page gives it: its numbers in
 * tabular figures, a column of numbers set to the right with its heading. It scrolls sideways on
 * its own when it is wider than the panel: it then takes the focus, so a keyboard scrolls it too.
 */
export function ExampleTable({ rows, label }: { rows: string[][]; label: string }) {
  const [head = [], ...body] = rows;
  const numeric = head.map(
    (_, j) => body.length > 0 && body.every((row) => NUMBER.test((row[j] ?? "").trim())),
  );
  const align = (j: number) => (numeric[j] ? "text-right" : "text-left");
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: a region that may scroll sideways must be reachable by keyboard
    <section aria-label={label} tabIndex={0} className="overflow-x-auto">
      <table className="w-full text-[0.8125rem] tabular-nums">
        <thead className="text-xs text-muted-foreground">
          <tr>
            {head.map((cell, j) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: columns of a fixed table
              <th key={j} scope="col" className={`px-3.5 py-1.5 font-medium ${align(j)}`}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: rows of a fixed table
            <tr key={i} className="border-t border-line-soft">
              {row.map((cell, j) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: columns of a fixed table
                <td key={j} className={`px-3.5 py-1.5 whitespace-nowrap ${align(j)}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
