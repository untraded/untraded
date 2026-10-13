// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: MIT

// Reference averages from HLTV's public Rating 1.0 definition.
const AVG_KPR = 0.679;
const AVG_SPR = 0.317;
const AVG_MULTIKILL = 1.277;

export interface MatchTotals {
  rounds: number;
  kills: number;
  deaths: number;
  /** Number of rounds with exactly N kills, keyed by N (1 to 5). */
  multikills: Partial<Record<1 | 2 | 3 | 4 | 5, number>>;
}

/** HLTV Rating 1.0 computed from match totals. */
export function ratingHltv1({ rounds, kills, deaths, multikills }: MatchTotals): number {
  if (!(rounds > 0)) throw new RangeError("rounds must be positive");
  let multikillPoints = 0;
  for (const [key, count] of Object.entries(multikills)) {
    const n = Number(key);
    if (!Number.isInteger(n) || n < 1 || n > 5) {
      throw new RangeError("multikills keys must be between 1 and 5");
    }
    multikillPoints += n * n * (count ?? 0);
  }
  const killRating = kills / rounds / AVG_KPR;
  const survivalRating = (rounds - deaths) / rounds / AVG_SPR;
  const multikillRating = multikillPoints / rounds / AVG_MULTIKILL;
  return (killRating + 0.7 * survivalRating + multikillRating) / 2.7;
}
