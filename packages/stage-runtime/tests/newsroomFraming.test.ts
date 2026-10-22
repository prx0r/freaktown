import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { NEWS_STUDIO, NEWSROOM_BLENDER_VARIANTS } from '../src/sets/definitions';
import { resolveCameraCue, seatHead } from '../src/sets/camera';
import type { SetDefinition, Vec3 } from '../src/sets/types';

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const norm = (a: Vec3): Vec3 => { const l = Math.hypot(...a); return [a[0] / l, a[1] / l, a[2] / l]; };

/** Vertical NDC (-1 bottom .. +1 top) of a world point seen by a look-at camera with vertical fov. */
function ndcY(pos: Vec3, target: Vec3, fovDeg: number, p: Vec3): number {
  const f = norm(sub(target, pos));
  const right = norm([-f[2], 0, f[0]]);
  const up: Vec3 = [right[1] * f[2] - right[2] * f[1], right[2] * f[0] - right[0] * f[2], right[0] * f[1] - right[1] * f[0]];
  const d = sub(p, pos);
  return dot(d, up) / dot(d, f) / Math.tan((fovDeg * Math.PI) / 360);
}

const withEyes = (def: SetDefinition, eye: number): SetDefinition => ({ ...def, seats: def.seats.map((s) => ({ ...s, eyeHeight: eye })) });

describe('newsroom close-up framing (eyeLineFraming)', () => {
  it('news studio frames seat shots from the measured eye line', () => {
    expect(NEWS_STUDIO.eyeLineFraming).toBe(true);
  });

  for (const eye of [1.03, 1.28]) {
    it(`anchor1-single puts eyes at ${eye} m on the upper third`, () => {
      const def = withEyes(NEWS_STUDIO, eye);
      const shot = resolveCameraCue(def, 'anchor1-single');
      const s = def.seats.find((x) => x.id === 'anchor1')!;
      const y = ndcY(shot.position, shot.target, shot.fov, seatHead(s));
      expect(y).toBeGreaterThan(0.3);
      expect(y).toBeLessThan(0.37);
    });
  }

  it('without a measured eye line the generic head height is used (other sets unchanged)', () => {
    const s = NEWS_STUDIO.seats[0];
    expect(seatHead(s)[1]).toBeCloseTo(1.3);
    expect(seatHead({ ...s, eyeHeight: 1.03 })[1]).toBeCloseTo(1.03);
  });
});

describe('Blender newsroom variants', () => {
  it('news studio lists the baked GLBs and each file ships with the live app', () => {
    const v = NEWS_STUDIO.environment.variants!;
    expect(v.ids).toEqual(NEWSROOM_BLENDER_VARIANTS);
    for (const id of v.ids) {
      const f = path.resolve(__dirname, '../../../apps/live/public', v.url.replace('{id}', id));
      expect(fs.existsSync(f), f).toBe(true);
      const head = fs.readFileSync(f).subarray(0, 4).toString('latin1');
      expect(head).toBe('glTF');
      expect(fs.statSync(f).size).toBeLessThan(15 * 1024 * 1024);
    }
  });

  it('every GLB carries the blank wall slot the web paints and both seat chairs', () => {
    for (const id of NEWSROOM_BLENDER_VARIANTS) {
      const buf = fs.readFileSync(path.resolve(__dirname, '../../../apps/live/public/stage-sets', `newsroom-${id}.glb`));
      const len = buf.readUInt32LE(12);
      const json = JSON.parse(buf.subarray(20, 20 + len).toString('utf8'));
      const names = new Set<string>([...json.nodes.map((n: { name?: string }) => n.name ?? ''), ...json.materials.map((m: { name?: string }) => m.name ?? '')]);
      for (const n of ['news_wall_screen', 'news_desk_brand', 'news_chair_anchor1', 'news_chair_anchor2', 'cam_wide', 'cam_close']) {
        expect(names.has(n), `${id}: ${n}`).toBe(true);
      }
    }
  });
});
