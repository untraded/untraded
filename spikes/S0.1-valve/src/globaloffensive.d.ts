// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only

// Minimal typings for the parts of node-globaloffensive used by this spike.
declare module "globaloffensive" {
  import type { EventEmitter } from "node:events";
  import type SteamUser from "steam-user";

  export interface RoundStats {
    /** Demo URL (http://replayNNN.valve.net/730/<matchid>_<n>.dem.bz2) on the last entry. */
    map?: string;
    match_duration?: number;
    team_scores?: number[];
  }

  export interface MatchInfo {
    matchid?: string | number;
    matchtime?: number;
    roundstatsall?: RoundStats[];
  }

  export default class GlobalOffensive extends EventEmitter {
    constructor(steamUser: SteamUser);
    readonly haveGCSession: boolean;
    requestGame(shareCode: string): void;
    on(event: "connectedToGC", listener: () => void): this;
    on(event: "disconnectedFromGC", listener: (reason: number) => void): this;
    on(event: "matchList", listener: (matches: MatchInfo[]) => void): this;
    once(event: "connectedToGC", listener: () => void): this;
    once(event: "matchList", listener: (matches: MatchInfo[]) => void): this;
    removeListener(event: string, listener: (...args: never[]) => void): this;
  }
}
