// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// An invented team for the team mode preview: its people, a few lineups, execs and strats, and
// tactical numbers. Every name and figure here is made up; positions are plausible, not measured.

import type { Access, Exec, Lineup, Matrix, Member, Strat } from "./types";

export const TEAM = { name: "Nightfall", tag: "NF" };

export const MEMBERS: Member[] = [
  { id: "ayla", name: "Ayla", role: "owner", roster: "starter", inGame: ["igl", "support"] },
  { id: "brann", name: "Brann", role: "player", roster: "starter", inGame: ["entry"] },
  { id: "kova", name: "Kova", role: "player", roster: "starter", inGame: ["awp"] },
  { id: "lumi", name: "Lumi", role: "player", roster: "starter", inGame: ["support", "anchor"] },
  { id: "sarn", name: "Sarn", role: "player", roster: "starter", inGame: ["lurker"] },
  { id: "teo", name: "Teo", role: "player", roster: "standin", inGame: ["entry", "rotator"] },
  { id: "vex", name: "Vex", role: "player", roster: "standin", inGame: ["awp"] },
  { id: "mara", name: "Mara", role: "coach", roster: null, inGame: [] },
  { id: "pim", name: "Pim", role: "viewer", roster: null, inGame: [] },
];

export const MATRIX: Matrix = {
  roster: { owner: "manage", coach: "edit", player: "view", viewer: "view" },
  lineups: { owner: "manage", coach: "manage", player: "edit", viewer: "view" },
  execs: { owner: "manage", coach: "manage", player: "view", viewer: "none" },
  strats: { owner: "manage", coach: "edit", player: "view", viewer: "none" },
  stats: { owner: "manage", coach: "view", player: "view", viewer: "view" },
};

const TEAM_ONLY: Access = { view: ["coach", "player"], edit: ["coach"] };
const OPEN: Access = { view: ["coach", "player", "viewer"], edit: ["coach", "player"] };
const STAFF: Access = { view: ["coach"], edit: ["coach"] };

export const LINEUPS: Lineup[] = [
  {
    id: "l-mirage-window",
    map: "mirage",
    side: "T",
    site: "mid",
    grenade: "smoke",
    title: { fr: "Smoke fenêtre depuis le spawn T", en: "Window smoke from T spawn" },
    from: {
      fr: "Coin du mur du spawn, pied contre la caisse",
      en: "Spawn wall corner, foot on the crate",
    },
    aim: { fr: "Antenne gauche au-dessus du toit", en: "Left antenna above the roof" },
    throw: "jump",
    setpos: "setpos 1216.0 -202.0 -103.9; setang -26.4 -165.8 0",
    clip: null,
    author: "ayla",
    access: OPEN,
  },
  {
    id: "l-mirage-ct",
    map: "mirage",
    side: "T",
    site: "A",
    grenade: "smoke",
    title: { fr: "Smoke CT depuis les escaliers T", en: "CT smoke from T stairs" },
    from: {
      fr: "Haut des escaliers, contre la rambarde",
      en: "Top of the stairs, against the rail",
    },
    aim: { fr: "Coin de la cheminée", en: "Chimney corner" },
    throw: "stand",
    setpos: "setpos 512.0 -1290.0 -159.9; setang -37.0 -128.5 0",
    clip: null,
    author: "lumi",
    access: OPEN,
  },
  {
    id: "l-mirage-jungle",
    map: "mirage",
    side: "T",
    site: "A",
    grenade: "smoke",
    title: { fr: "Smoke jungle depuis le toit T", en: "Jungle smoke from T roof" },
    from: { fr: "Bord du toit, dans l'angle", en: "Roof edge, in the corner" },
    aim: { fr: "Haut de la fenêtre du palais", en: "Top of the palace window" },
    throw: "runjump",
    setpos: "setpos 1044.0 -1102.0 -95.9; setang -41.2 -143.0 0",
    clip: null,
    author: "lumi",
    access: OPEN,
  },
  {
    id: "l-mirage-a-flash",
    map: "mirage",
    side: "T",
    site: "A",
    grenade: "flash",
    title: { fr: "Flash pop A depuis la rampe", en: "A pop flash from ramp" },
    from: { fr: "Bas de la rampe, contre le mur gauche", en: "Bottom of ramp, left wall" },
    aim: { fr: "Haut de l'arche", en: "Top of the arch" },
    throw: "stand",
    setpos: "setpos 392.0 -1588.0 -159.9; setang -58.0 -110.2 0",
    clip: null,
    author: "brann",
    access: TEAM_ONLY,
  },
  {
    id: "l-mirage-b-molly",
    map: "mirage",
    side: "CT",
    site: "B",
    grenade: "molotov",
    title: { fr: "Molotov appartements depuis le site B", en: "Apartments molotov from B site" },
    from: { fr: "Derrière la benne", en: "Behind the dumpster" },
    aim: { fr: "Lampe au-dessus de la porte", en: "Lamp above the door" },
    throw: "stand",
    setpos: "setpos -1910.0 512.0 -95.9; setang -18.5 32.0 0",
    clip: null,
    author: "lumi",
    access: OPEN,
  },
  {
    id: "l-inferno-ct",
    map: "inferno",
    side: "T",
    site: "B",
    grenade: "smoke",
    title: { fr: "Smoke CT depuis la banane", en: "CT smoke from banana" },
    from: { fr: "Haut de la banane, contre le tonneau", en: "Top banana, against the barrel" },
    aim: { fr: "Croix du toit de l'église", en: "Cross on the church roof" },
    throw: "jump",
    setpos: "setpos 286.0 1904.0 152.0; setang -32.7 75.4 0",
    clip: null,
    author: "ayla",
    access: OPEN,
  },
  {
    id: "l-inferno-coffins",
    map: "inferno",
    side: "T",
    site: "B",
    grenade: "molotov",
    title: { fr: "Molotov cercueils", en: "Coffins molotov" },
    from: { fr: "Sable de la banane", en: "Banana sandbags" },
    aim: { fr: "Fenêtre haute à droite", en: "Top right window" },
    throw: "stand",
    setpos: "setpos 410.0 2120.0 140.0; setang -20.1 64.0 0",
    clip: null,
    author: "sarn",
    access: OPEN,
  },
  {
    id: "l-inferno-a-flash",
    map: "inferno",
    side: "T",
    site: "A",
    grenade: "flash",
    title: { fr: "Flash apparts pour le peek A", en: "Apartments flash for the A peek" },
    from: { fr: "Balcon des appartements", en: "Apartments balcony" },
    aim: { fr: "Bord du mur, au-dessus de la plante", en: "Wall edge, above the plant" },
    throw: "stand",
    setpos: "setpos 1616.0 -40.0 236.0; setang -61.0 -9.5 0",
    clip: null,
    author: "brann",
    access: TEAM_ONLY,
  },
  {
    id: "l-ancient-mid",
    map: "ancient",
    side: "T",
    site: "mid",
    grenade: "smoke",
    title: { fr: "Smoke mid depuis le spawn T", en: "Mid smoke from T spawn" },
    from: { fr: "Pilier gauche du spawn", en: "Left spawn pillar" },
    aim: { fr: "Pointe de la statue", en: "Statue tip" },
    throw: "jump",
    setpos: "setpos -480.0 -1810.0 -55.9; setang -30.8 86.0 0",
    clip: null,
    author: "ayla",
    access: OPEN,
  },
  {
    id: "l-ancient-b-he",
    map: "ancient",
    side: "CT",
    site: "B",
    grenade: "he",
    title: { fr: "HE rampe B à la sortie", en: "B ramp HE on the push" },
    from: { fr: "Fond du site B", en: "Back of B site" },
    aim: { fr: "Haut de la porte de la rampe", en: "Top of the ramp door" },
    throw: "walk",
    setpos: "setpos 1290.0 64.0 128.0; setang -12.0 -150.0 0",
    clip: null,
    author: "kova",
    access: STAFF,
  },
];

export const EXECS: Exec[] = [
  {
    id: "e-mirage-a",
    map: "mirage",
    site: "A",
    title: { fr: "A split rampe et palais", en: "A split, ramp and palace" },
    timing: "1:05",
    tasks: [
      {
        member: "ayla",
        task: { fr: "Smoke CT, puis connecteur", en: "CT smoke, then connector" },
        lineup: "l-mirage-ct",
      },
      {
        member: "lumi",
        task: { fr: "Smoke jungle", en: "Jungle smoke" },
        lineup: "l-mirage-jungle",
      },
      {
        member: "brann",
        task: { fr: "Entrée rampe sur la flash", en: "Ramp entry on the flash" },
        lineup: "l-mirage-a-flash",
      },
      {
        member: "sarn",
        task: { fr: "Palais, attend le contact", en: "Palace, waits for contact" },
      },
      {
        member: "kova",
        task: { fr: "AWP sur le mid, puis appartement", en: "AWP mid, then connector" },
      },
    ],
    steps: [
      { fr: "Fenêtre fumée dès la sortie du spawn.", en: "Window smoked out of spawn." },
      {
        fr: "À 1:10, les trois smokes partent ensemble.",
        en: "At 1:10, the three smokes go together.",
      },
      {
        fr: "Brann entre sur la flash, Sarn sort du palais au premier tir.",
        en: "Brann enters on the flash, Sarn swings palace on the first shot.",
      },
      {
        fr: "Pose par défaut, post-plant croisé jungle et palais.",
        en: "Default plant, crossfire jungle and palace.",
      },
    ],
    access: TEAM_ONLY,
  },
  {
    id: "e-mirage-b",
    map: "mirage",
    site: "B",
    title: { fr: "B rush appartements", en: "B apartments rush" },
    timing: "1:40",
    tasks: [
      { member: "brann", task: { fr: "Premier dans les apparts", en: "First through apartments" } },
      { member: "teo", task: { fr: "Deuxième, trade Brann", en: "Second, trades Brann" } },
      { member: "lumi", task: { fr: "Flash par-dessus le mur", en: "Flash over the wall" } },
      { member: "sarn", task: { fr: "Bloque le court", en: "Holds short" } },
      { member: "kova", task: { fr: "Fenêtre, puis dernier", en: "Window, then last" } },
    ],
    steps: [
      { fr: "Rush à la sortie du freeze, pas de retenue.", en: "Rush off the freeze, no hold." },
      { fr: "Deux flashs, une molotov sur le banc.", en: "Two flashes, a molotov on the bench." },
    ],
    access: OPEN,
  },
  {
    id: "e-inferno-b",
    map: "inferno",
    site: "B",
    title: { fr: "B lent par la banane", en: "Slow B through banana" },
    timing: "0:55",
    tasks: [
      { member: "ayla", task: { fr: "Smoke CT", en: "CT smoke" }, lineup: "l-inferno-ct" },
      {
        member: "sarn",
        task: { fr: "Molotov cercueils", en: "Coffins molotov" },
        lineup: "l-inferno-coffins",
      },
      { member: "brann", task: { fr: "Entrée sable", en: "Sandbags entry" } },
      { member: "lumi", task: { fr: "Flash pop pour Brann", en: "Pop flash for Brann" } },
      { member: "kova", task: { fr: "Lurk A apparts", en: "A apartments lurk" } },
    ],
    steps: [
      {
        fr: "Banane prise en début de round, utilitaires gardés.",
        en: "Banana taken early, utility kept.",
      },
      {
        fr: "Exec à 0:55, Kova coupe la rotation par les apparts.",
        en: "Exec at 0:55, Kova cuts the rotation through apartments.",
      },
    ],
    access: STAFF,
  },
];

export const STRATS: Strat[] = [
  {
    id: "s-mirage-default",
    map: "mirage",
    side: "T",
    kind: "default",
    title: { fr: "Défaut lent, contrôle du mid", en: "Slow default, mid control" },
    steps: [
      {
        member: "kova",
        text: { fr: "AWP top mid, ne pas peek fenêtre", en: "AWP top mid, no window peek" },
      },
      {
        member: "sarn",
        text: { fr: "Palais silencieux jusqu'à 1:00", en: "Quiet palace until 1:00" },
      },
      {
        member: "brann",
        text: { fr: "Info rampe, recule au contact", en: "Ramp info, falls back on contact" },
      },
      {
        member: "lumi",
        text: { fr: "Smoke fenêtre, puis B apparts", en: "Window smoke, then B apartments" },
      },
      {
        member: "ayla",
        text: { fr: "Lit le round, appelle le split", en: "Reads the round, calls the split" },
      },
    ],
    notes: {
      fr: "Si le mid tombe tôt, on part sur l'exec A split.",
      en: "If mid falls early, go into the A split exec.",
    },
    tags: ["mid", "slow"],
    access: TEAM_ONLY,
  },
  {
    id: "s-mirage-pistol",
    map: "mirage",
    side: "T",
    kind: "pistol",
    title: { fr: "Pistol B à cinq", en: "Five-man B pistol" },
    steps: [
      { member: "brann", text: { fr: "Premier, armure", en: "First in, armour" } },
      { member: "teo", text: { fr: "Deuxième, flash", en: "Second, flash" } },
      { member: "lumi", text: { fr: "Smoke court", en: "Short smoke" } },
      { member: "ayla", text: { fr: "Flash banc", en: "Bench flash" } },
      { member: "kova", text: { fr: "Dernier, garde le pistolet", en: "Last, keeps the pistol" } },
    ],
    notes: {
      fr: "Contre une équipe qui joue A à trois, on passe en A.",
      en: "Against a team stacking A with three, go A.",
    },
    tags: ["pistol", "rush"],
    access: OPEN,
  },
  {
    id: "s-mirage-retake",
    map: "mirage",
    side: "CT",
    kind: "retake",
    title: { fr: "Retake A en 3 contre 2", en: "A retake in a 3v2" },
    steps: [
      { member: "kova", text: { fr: "Jungle, flash pour soi", en: "Jungle, self flash" } },
      { member: "lumi", text: { fr: "Molotov sous le site", en: "Molotov under the site" } },
      { member: "ayla", text: { fr: "Entrée par CT avec Lumi", en: "Enter from CT with Lumi" } },
    ],
    notes: {
      fr: "Toujours deux flashs avant d'entrer.",
      en: "Always two flashes before going in.",
    },
    tags: ["retake"],
    access: OPEN,
  },
  {
    id: "s-inferno-eco",
    map: "inferno",
    side: "T",
    kind: "eco",
    title: { fr: "Éco stack apparts", en: "Apartments eco stack" },
    steps: [
      {
        member: "brann",
        text: { fr: "Premier à la sortie des apparts", en: "First out of apartments" },
      },
      { member: "ayla", text: { fr: "Garde l'argent si personne", en: "Saves if nobody shows" } },
    ],
    notes: {
      fr: "But : une arme et de l'argent pour le round suivant.",
      en: "Goal: one rifle and money for the next round.",
    },
    tags: ["eco"],
    access: STAFF,
  },
  {
    id: "s-ancient-antieco",
    map: "ancient",
    side: "CT",
    kind: "antieco",
    title: { fr: "Anti-éco, on recule", en: "Anti-eco, play back" },
    steps: [
      { member: "kova", text: { fr: "Pas d'AWP, un fusil", en: "No AWP, a rifle" } },
      { member: "lumi", text: { fr: "B en retrait, pas de peek", en: "Deep B, no peek" } },
    ],
    notes: { fr: "Ne pas offrir de duel au fusil à pompe.", en: "Give no shotgun duels." },
    tags: ["anti-eco"],
    access: OPEN,
  },
];

/** Tactical numbers of the last 30 days (invented). */
export const STATS = {
  matches: 18,
  rounds: 412,
  sites: [
    { map: "mirage", site: "A", tried: 41, won: 26 },
    { map: "mirage", site: "B", tried: 33, won: 15 },
    { map: "inferno", site: "A", tried: 22, won: 9 },
    { map: "inferno", site: "B", tried: 37, won: 23 },
    { map: "ancient", site: "A", tried: 19, won: 10 },
    { map: "ancient", site: "B", tried: 24, won: 14 },
  ],
  execs: [
    { exec: "e-mirage-a", run: 17, won: 12 },
    { exec: "e-mirage-b", run: 11, won: 4 },
    { exec: "e-inferno-b", run: 14, won: 9 },
  ],
  setups: [
    { map: "mirage", setup: { fr: "2 A, 1 mid, 2 B", en: "2 A, 1 mid, 2 B" }, rounds: 54, won: 31 },
    {
      map: "mirage",
      setup: { fr: "3 A, AWP fenêtre", en: "3 A, window AWP" },
      rounds: 22,
      won: 10,
    },
    {
      map: "inferno",
      setup: { fr: "2 apparts, 1 arche, 2 B", en: "2 apartments, 1 arch, 2 B" },
      rounds: 47,
      won: 30,
    },
  ],
  postplant: [
    { situation: "2v2", rounds: 14, won: 9 },
    { situation: "3v2", rounds: 11, won: 9 },
    { situation: "2v3", rounds: 9, won: 3 },
  ],
  retakes: [
    { situation: "3v2", rounds: 12, won: 6 },
    { situation: "4v3", rounds: 8, won: 5 },
    { situation: "2v2", rounds: 10, won: 3 },
  ],
  economy: [
    { buy: "pistol", rounds: 36, won: 21 },
    { buy: "eco", rounds: 44, won: 6 },
    { buy: "force", rounds: 39, won: 14 },
    { buy: "full", rounds: 293, won: 171 },
  ],
  /** Who traded whose death: trades[a][b] = times a traded b's death. */
  trades: {
    ayla: { ayla: 0, brann: 9, kova: 2, lumi: 4, sarn: 1 },
    brann: { ayla: 3, brann: 0, kova: 1, lumi: 2, sarn: 0 },
    kova: { ayla: 2, brann: 6, kova: 0, lumi: 3, sarn: 1 },
    lumi: { ayla: 5, brann: 11, kova: 2, lumi: 0, sarn: 2 },
    sarn: { ayla: 1, brann: 1, kova: 0, lumi: 1, sarn: 0 },
  } as Record<string, Record<string, number>>,
};
