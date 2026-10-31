// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
"use client";

import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { EXECS, MEMBERS, STATS } from "@/lib/team-preview/data";
import { text } from "@/lib/team-preview/types";
import { mapLabel } from "./parts";

const STARTERS = MEMBERS.filter((m) => m.roster === "starter");

/** One line of a success table: a name, "won of tried", and a bar of the rate. */
function Rate({ name, won, tried }: { name: ReactNode; won: number; tried: number }) {
  const t = useTranslations("team");
  const rate = tried === 0 ? 0 : won / tried;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_5.5rem_3rem] items-center gap-x-3 border-t border-line-soft py-1.5 text-sm first:border-t-0 sm:grid-cols-[minmax(0,1fr)_6rem_8rem_3rem]">
      <span className="min-w-0 truncate">{name}</span>
      <span className="text-right text-xs text-muted-foreground tabular-nums">
        {t("stats.won", { won, tried })}
      </span>
      <span
        aria-hidden="true"
        className="hidden h-2 overflow-hidden rounded-full bg-muted sm:block"
      >
        <span className="block h-full bg-foreground/70" style={{ width: `${rate * 100}%` }} />
      </span>
      <span className="text-right font-semibold tabular-nums">{Math.round(rate * 100)} %</span>
    </li>
  );
}

function Box({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
    </section>
  );
}

/** The team's tactical numbers (invented): where it wins, with what, and who trades whom. */
export function StatsView() {
  const t = useTranslations("team");
  const locale = useLocale();
  const most = Math.max(...Object.values(STATS.trades).flatMap((row) => Object.values(row)));
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        {t("stats.lead", { matches: STATS.matches, rounds: STATS.rounds })}
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        <Box title={t("stats.sites")}>
          <ul>
            {STATS.sites.map((s) => (
              <Rate
                key={`${s.map}-${s.site}`}
                name={`${mapLabel(s.map)} ${s.site}`}
                won={s.won}
                tried={s.tried}
              />
            ))}
          </ul>
        </Box>
        <Box title={t("stats.execs")}>
          <ul>
            {STATS.execs.map((e) => {
              const exec = EXECS.find((x) => x.id === e.exec);
              return (
                <Rate
                  key={e.exec}
                  name={exec ? `${mapLabel(exec.map)} · ${text(exec.title, locale)}` : e.exec}
                  won={e.won}
                  tried={e.run}
                />
              );
            })}
          </ul>
        </Box>
        <Box title={t("stats.setups")}>
          <ul>
            {STATS.setups.map((s) => (
              <Rate
                key={text(s.setup, "en")}
                name={`${mapLabel(s.map)} · ${text(s.setup, locale)}`}
                won={s.won}
                tried={s.rounds}
              />
            ))}
          </ul>
        </Box>
        <Box title={t("stats.economy")}>
          <ul>
            {STATS.economy.map((e) => (
              <Rate key={e.buy} name={t(`stats.buys.${e.buy}`)} won={e.won} tried={e.rounds} />
            ))}
          </ul>
        </Box>
        <Box title={t("stats.postplant")}>
          <ul>
            {STATS.postplant.map((p) => (
              <Rate key={p.situation} name={p.situation} won={p.won} tried={p.rounds} />
            ))}
          </ul>
        </Box>
        <Box title={t("stats.retakes")}>
          <ul>
            {STATS.retakes.map((r) => (
              <Rate key={r.situation} name={r.situation} won={r.won} tried={r.rounds} />
            ))}
          </ul>
        </Box>
      </div>
      <Box title={t("stats.trades")} hint={t("stats.tradesHint")}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[22rem] text-sm tabular-nums">
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th scope="col" className="px-2 py-1.5 text-left font-medium">
                  <span className="sr-only">{t("stats.trader")}</span>
                </th>
                {STARTERS.map((m) => (
                  <th key={m.id} scope="col" className="px-2 py-1.5 text-center font-medium">
                    {m.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {STARTERS.map((row) => (
                <tr key={row.id}>
                  <th scope="row" className="px-2 py-1 text-left font-semibold">
                    {row.name}
                  </th>
                  {STARTERS.map((col) => {
                    const count = STATS.trades[row.id]?.[col.id] ?? 0;
                    return (
                      <td key={col.id} className="p-0.5 text-center">
                        {row.id === col.id ? (
                          <span className="block py-1.5 text-muted-foreground">–</span>
                        ) : (
                          <span
                            className="block rounded-sm py-1.5"
                            style={{
                              backgroundColor: `color-mix(in srgb, var(--foreground) ${Math.round((count / most) * 28)}%, transparent)`,
                            }}
                          >
                            {count}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Box>
    </div>
  );
}
