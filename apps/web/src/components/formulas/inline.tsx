// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import Link from "next/link";
import type { ReactNode } from "react";

const DOCS = "https://github.com/untraded/untraded/blob/main/docs/";

/**
 * Where a link of a metric page leads on the site: another metric's page opens its formula, the
 * shared conventions are on the formulas page, other documents of the repository open on GitHub.
 */
export function linkTarget(href: string): { href: string; external: boolean } {
  if (/^https?:/.test(href)) return { href, external: true };
  if (href.startsWith("README.md")) return { href: "/formulas#conventions", external: false };
  if (href.startsWith("../")) return { href: `${DOCS}${href.slice(3)}`, external: true };
  const page = href.match(/^([a-z0-9_]+\.[a-z0-9_]+)\.md$/);
  if (page) return { href: `/formulas/${page[1]}`, external: false };
  return { href: `${DOCS}metrics/${href}`, external: true };
}

/** The inline Markdown of the generated pages: `code`, **bold**, [links](…). Nothing else. */
export function Inline({ text }: { text: string }) {
  const parts: ReactNode[] = [];
  const token = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  for (const match of text.matchAll(token)) {
    const at = match.index ?? 0;
    if (at > last) parts.push(text.slice(last, at));
    const [whole, code, bold, label, href] = match;
    if (code !== undefined) {
      parts.push(
        <code
          key={at}
          translate="no"
          className="rounded-[3px] bg-muted px-1 font-mono text-[0.9em]"
        >
          {code}
        </code>,
      );
    } else if (bold !== undefined) {
      parts.push(
        <strong key={at} className="font-semibold">
          {bold}
        </strong>,
      );
    } else if (label !== undefined && href !== undefined) {
      const target = linkTarget(href);
      const inner = <Inline text={label} />;
      parts.push(
        target.external ? (
          <a
            key={at}
            href={target.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-link underline underline-offset-3"
          >
            {inner}
          </a>
        ) : (
          <Link key={at} href={target.href} className="text-link underline underline-offset-3">
            {inner}
          </Link>
        ),
      );
    }
    last = at + whole.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
