// SPDX-FileCopyrightText: 2026 The Untraded Authors
// SPDX-License-Identifier: AGPL-3.0-only
//
// The 2D viewer's drawing, with PixiJS (WebGL): the radar under everything, then smokes and fires,
// grenades in flight, deaths, the bomb and the players. Loaded on the client only, from the viewer.

import type { Application, Container, Graphics, Sprite, Text, Texture } from "pixi.js";
import {
  angleBetween,
  between,
  bombCarrier,
  FIRE_RADIUS,
  type Frame,
  frameOf,
  hasLevels,
  type Level,
  levelOf,
  nearest,
  RADAR_MAPS,
  type Replay,
  SMOKE_RADIUS,
  sampleAt,
  TWO_LEVELS,
} from "@/lib/replay";

/** The theme's colours, as the page resolves them (see `readColors`). */
export interface SceneColors {
  radar: string;
  foreground: string;
  muted: string;
  card: string;
  ct: string;
  t: string;
  highlight: string;
  loss: string;
}

export interface SceneState {
  tick: number;
  /** The player to highlight (ring, bold name), if any. */
  focus: string | null;
  level: Level;
}

export interface Scene {
  draw: (state: SceneState) => void;
  resize: (size: number) => void;
  setColors: (colors: SceneColors) => void;
  destroy: () => void;
}

/** Draws a round in `host`, a square `size` pixels wide. Rejects when WebGL is not available. */
export async function createScene(
  host: HTMLElement,
  replay: Replay,
  size: number,
  initial: SceneColors,
): Promise<Scene> {
  const PIXI = await import("pixi.js");
  const app: Application = new PIXI.Application();
  await app.init({
    width: size,
    height: size,
    backgroundAlpha: 0,
    antialias: true,
    autoDensity: true,
    resolution: window.devicePixelRatio || 1,
    preference: "webgl",
  });
  app.ticker.stop();
  app.canvas.setAttribute("aria-hidden", "true");
  app.canvas.style.display = "block";
  app.canvas.style.width = "100%";
  app.canvas.style.height = "100%";
  host.appendChild(app.canvas);

  let colors = initial;
  let scale = size / 1024;
  const frame: Frame = frameOf(replay);
  const two = hasLevels(replay);

  // The radars: ours, white shapes tinted to the theme, one per level.
  const radars: Partial<Record<Level, Sprite>> = {};
  if (frame.radar && RADAR_MAPS.has(replay.map)) {
    const load = async (level: Level) => {
      const src = `/radars/${replay.map}${level === "lower" ? "_lower" : ""}.svg`;
      try {
        const texture: Texture = await PIXI.Assets.load({ src, data: { resolution: 2 } });
        const sprite = new PIXI.Sprite(texture);
        sprite.width = 1024;
        sprite.height = 1024;
        radars[level] = sprite;
      } catch {
        // No radar: the round is drawn on the plain background.
      }
    };
    await Promise.all([
      load("upper"),
      ...(two && TWO_LEVELS.has(replay.map) ? [load("lower")] : []),
    ]);
  }
  const ground: Container = new PIXI.Container();
  for (const sprite of Object.values(radars)) if (sprite) ground.addChild(sprite);
  const zones: Graphics = new PIXI.Graphics();
  const marks: Graphics = new PIXI.Graphics();
  const bodies: Graphics = new PIXI.Graphics();
  const labels: Container = new PIXI.Container();
  app.stage.addChild(ground, zones, marks, bodies, labels);

  const names = new Map<string, Text>();
  for (const player of replay.players) {
    const text = new PIXI.Text({
      text: player.name,
      style: {
        fontFamily: "IBM Plex Sans, system-ui, sans-serif",
        fontSize: 11,
        fontWeight: "500",
      },
      resolution: (window.devicePixelRatio || 1) * 1.5,
    });
    text.anchor.set(0.5, 1);
    labels.addChild(text);
    names.set(player.steamid, text);
  }

  const at = (x: number, y: number): [number, number] => {
    const [px, py] = frame.toPixel(x, y);
    return [px * scale, py * scale];
  };
  const sideColor = (side: string | null) => (side === "CT" ? colors.ct : colors.t);
  const planted = replay.bomb.events.find((e) => e.type === "planted");
  const exploded = replay.bomb.events.find((e) => e.type === "exploded");

  function draw({ tick, focus, level }: SceneState) {
    ground.scale.set(scale);
    for (const [key, sprite] of Object.entries(radars) as [Level, Sprite][]) {
      // Only the level shown: when its radar is missing, no radar rather than the other level's.
      sprite.visible = !two || key === level;
      sprite.tint = colors.radar;
    }
    const sample = sampleAt(replay.ticks, tick);
    const unit = frame.scale * scale;
    // What stands on the other level is drawn faded, as its players are (hollow).
    const away = (z: number | null | undefined) =>
      two && z !== null && z !== undefined && levelOf(replay, z) !== level;
    const AWAY = 0.35;
    zones.clear();
    marks.clear();
    bodies.clear();

    // Smokes and fires, under everything else.
    for (const g of replay.grenades) {
      if (!g.detonate || g.detonate_tick === null || tick < g.detonate_tick) continue;
      if (g.end_tick !== null && tick > g.end_tick) continue;
      const [x, y] = at(g.detonate[0], g.detonate[1]);
      const dim = away(g.detonate[2]) ? AWAY : 1;
      if (g.type === "smoke") {
        zones.circle(x, y, SMOKE_RADIUS * unit).fill({ color: colors.muted, alpha: 0.42 * dim });
      } else if (g.type === "molotov" || g.type === "incendiary") {
        zones.circle(x, y, FIRE_RADIUS * unit).fill({ color: colors.t, alpha: 0.3 * dim });
      }
    }

    // Grenades in flight: their path so far, dotted, and where they are.
    for (const g of replay.grenades) {
      if (tick < g.throw_tick || (g.detonate_tick !== null && tick >= g.detonate_tick)) continue;
      const color = sideColor(g.side);
      let last: { point: [number, number]; away: boolean } | null = null;
      g.path.ticks.forEach((t, k) => {
        if (t > tick) return;
        const point = at(g.path.x[k] ?? 0, g.path.y[k] ?? 0);
        const off = away(g.path.z[k]);
        if (k % 2 === 0) {
          marks.circle(point[0], point[1], 1).fill({ color, alpha: 0.7 * (off ? AWAY : 1) });
        }
        last = { point, away: off };
      });
      const end = last as { point: [number, number]; away: boolean } | null;
      if (end) {
        const [x, y] = end.point;
        if (end.away) marks.circle(x, y, 2.5).stroke({ width: 1.25, color, alpha: AWAY + 0.15 });
        else marks.circle(x, y, 2.5).fill({ color });
      }
    }

    // Flashes and HE: a short burst where they go off.
    for (const g of replay.grenades) {
      if (!g.detonate || g.detonate_tick === null || (g.type !== "flash" && g.type !== "he"))
        continue;
      const since = (tick - g.detonate_tick) / replay.tickrate;
      if (since < 0 || since > 0.6) continue;
      const [x, y] = at(g.detonate[0], g.detonate[1]);
      const k = since / 0.6;
      const dim = away(g.detonate[2]) ? AWAY : 1;
      const radius = 6 + k * (g.type === "flash" ? 26 : 18);
      const color = g.type === "flash" ? colors.foreground : colors.loss;
      if (g.type === "flash") {
        marks.circle(x, y, radius).fill({ color, alpha: (1 - k) * 0.3 * dim });
      }
      marks.circle(x, y, radius).stroke({ width: 2, color, alpha: (1 - k) * dim });
    }

    // The bomb, once planted: it blinks, faster after it explodes it stays.
    if (planted && tick >= planted.tick && replay.bomb.planted_at) {
      const [x, y] = at(replay.bomb.planted_at[0], replay.bomb.planted_at[1]);
      const on =
        exploded && tick >= exploded.tick
          ? true
          : Math.floor((tick - planted.tick) / (replay.tickrate / 2)) % 2 === 0;
      const diamond = [x, y - 7, x + 7, y, x, y + 7, x - 7, y];
      if (away(replay.bomb.planted_at[2])) {
        marks.poly(diamond).stroke({ width: 1.5, color: colors.loss, alpha: on ? 0.6 : 0.3 });
      } else {
        marks.poly(diamond).fill({ color: colors.loss, alpha: on ? 1 : 0.45 });
      }
    }

    // Deaths: a cross where the player fell.
    for (const kill of replay.kills) {
      if (kill.tick > tick) continue;
      const victim = replay.players.find((p) => p.steamid === kill.victim);
      if (!victim) continue;
      const [x, y] = at(kill.victim_x, kill.victim_y);
      const off = away(kill.victim_z);
      marks
        .moveTo(x - 5, y - 5)
        .lineTo(x + 5, y + 5)
        .moveTo(x + 5, y - 5)
        .lineTo(x - 5, y + 5)
        .stroke({
          width: off ? 1.25 : 2,
          color: sideColor(victim.side),
          alpha: off ? AWAY : 0.75,
        });
    }

    // Players, the highlighted one on top.
    const carrier = planted && tick >= planted.tick ? null : bombCarrier(replay, tick);
    const order = [...replay.players].sort(
      (a, b) => Number(a.steamid === focus) - Number(b.steamid === focus),
    );
    for (const player of order) {
      const name = names.get(player.steamid);
      const x = between(player.x, sample);
      const y = between(player.y, sample);
      if (!nearest(player.alive, sample) || x === null || y === null) {
        if (name) name.visible = false;
        continue;
      }
      const [cx, cy] = at(x, y);
      const away = two && levelOf(replay, between(player.z, sample)) !== level;
      const color = sideColor(player.side);
      const alpha = away ? 0.4 : 1;
      const yaw = angleBetween(player.yaw, sample);
      if (yaw !== null) {
        const a = (-yaw * Math.PI) / 180;
        bodies
          .moveTo(cx, cy)
          .lineTo(cx + Math.cos(a) * 15, cy + Math.sin(a) * 15)
          .stroke({ width: 2, color, alpha });
      }
      if (away) {
        bodies.circle(cx, cy, 6).stroke({ width: 2, color, alpha });
      } else {
        bodies.circle(cx, cy, 6.5).fill({ color }).stroke({ width: 1.5, color: colors.card });
        const flash = between(player.flash, sample) ?? 0;
        if (flash > 0.3)
          bodies
            .circle(cx, cy, 4)
            .fill({ color: colors.foreground, alpha: Math.min(0.8, flash / 3) });
      }
      if (player.steamid === focus)
        bodies.circle(cx, cy, 11).stroke({ width: 2.5, color: colors.highlight });
      if (player.steamid === carrier)
        bodies.rect(cx + 6, cy - 11, 6, 6).fill({ color: colors.loss, alpha });
      const hp = nearest(player.hp, sample) ?? 0;
      bodies.rect(cx - 9, cy + 10, 18, 3).fill({ color: colors.card, alpha });
      bodies
        .rect(cx - 9, cy + 10, (18 * Math.max(0, Math.min(100, hp))) / 100, 3)
        .fill({ color: hp > 40 ? color : colors.loss, alpha });
      if (name) {
        name.visible = true;
        name.position.set(cx, cy - 10);
        name.alpha = alpha;
        name.style.fill = player.steamid === focus ? colors.foreground : colors.muted;
        name.style.fontWeight = player.steamid === focus ? "600" : "500";
      }
    }
    app.render();
  }

  return {
    draw,
    resize(next) {
      scale = next / 1024;
      app.renderer.resize(next, next);
    },
    setColors(next) {
      colors = next;
    },
    destroy() {
      app.destroy({ removeView: true }, { children: true });
    },
  };
}
