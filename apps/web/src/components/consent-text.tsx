// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";
import { operator } from "@/lib/site";

const SECTIONS = ["s1", "s2", "s3", "s4", "s5", "s6", "s7"];

/** Whether the site has this version of the consent text in its messages. */
export async function knowsConsentText(version: string): Promise<boolean> {
  return (await getTranslations("consent")).has(`v${version}.title`);
}

/**
 * The consent text of one version, as the player agrees to it (`messages/*.json`, `consent`).
 * The operator, the hosting and how long raw demos stay come from the site's settings.
 */
export async function ConsentText({ version }: { version: string }) {
  const t = await getTranslations("consent");
  const welcome = await getTranslations("welcome");
  const key = `v${version}`;
  const site = operator();
  const unset = welcome("operatorUnset");
  const values = {
    operator: site.name ?? unset,
    email: site.email ?? welcome("emailUnset"),
    hosting: site.hosting ?? "",
    days: site.retentionDays ?? 0,
    b: (chunks: ReactNode) => <strong className="font-semibold">{chunks}</strong>,
  };
  const line = (path: string) => t.rich(`${key}.${path}`, values);
  // The items of a section, in order: `i1`, `i2`… with the variants the settings choose.
  const items = (section: string): string[] => {
    const raw = t.raw(`${key}.${section}`) as Record<string, string>;
    return Object.keys(raw)
      .filter((name) => /^i\d+$/.test(name))
      .map((name) => {
        if (section === "s3" && name === "i4" && !site.hosting) return "hostingUnknown";
        if (section === "s4" && name === "i1") {
          if (site.retentionDays === null) return "i1Kept";
          if (site.retentionDays === 0) return "i1Parsed";
        }
        return name;
      });
  };
  return (
    <article className="flex max-w-[70ch] flex-col gap-4 text-[0.9375rem] leading-relaxed">
      <h2 className="text-xl font-semibold text-balance">{t(`${key}.title`)}</h2>
      <p>{line("lead")}</p>
      <p>{line("controller")}</p>
      {SECTIONS.map((section) => {
        const raw = t.raw(`${key}.${section}`) as Record<string, string>;
        return (
          <section key={section} className="flex flex-col gap-2">
            <h3 className="font-semibold">{t(`${key}.${section}.title`)}</h3>
            {"lead" in raw && <p>{line(`${section}.lead`)}</p>}
            {"body" in raw && <p>{line(`${section}.body`)}</p>}
            {items(section).length > 0 && (
              <ul className="flex list-disc flex-col gap-1.5 pl-5 marker:text-muted-foreground">
                {items(section).map((item) => (
                  <li key={item}>{line(`${section}.${item}`)}</li>
                ))}
              </ul>
            )}
            {"after" in raw && <p>{line(`${section}.after`)}</p>}
          </section>
        );
      })}
    </article>
  );
}
