import { describe, expect, it } from 'vitest';
import {
  SET_REGISTRY, SetRegistry, findSeat, resolveCameraCue, isValidCameraCue, seatHead, ActiveSpeakerDirector,
  textMouth, estimateLineMs, NEWS_STUDIO, PODCAST, POKER_TABLE, COMEDY_CLUB, newsDemo, podcastDemo, type SetDefinition,
} from '../src/sets';

const dist = (a: number[], b: number[]) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

describe('set registry', () => {
  it('ships comedy club as set #1 plus news, podcast, poker', () => {
    expect(SET_REGISTRY.list().map((s) => s.id)).toEqual(['comedy-club', 'news-studio', 'podcast', 'poker-table']);
  });
  it('every set has a procedural builder and valid default camera', () => {
    for (const d of SET_REGISTRY.list()) {
      expect(d.environment.builder).toBe(d.id);
      expect(() => resolveCameraCue(d, d.defaultCamera)).not.toThrow();
      for (const c of d.controlCameras) expect(isValidCameraCue(d, c)).toBe(true);
    }
  });
  it('rejects duplicate seats and cameras bound to unknown seats', () => {
    const r = new SetRegistry();
    const bad: SetDefinition = { ...PODCAST, id: 'bad', seats: [PODCAST.seats[0], PODCAST.seats[0]] };
    expect(() => r.register(bad)).toThrow(/duplicate seat/);
    const bad2: SetDefinition = { ...PODCAST, id: 'bad2', cameras: { wide: PODCAST.cameras.wide, x: { seat: 'nope', position: [0, 0, 1], target: [0, 0, 0], fov: 30 } } };
    expect(() => r.register(bad2)).toThrow(/unknown seat/);
    expect(() => SET_REGISTRY.require('nope')).toThrow(/unknown set/);
  });
  it('finds seats by id, role and index', () => {
    expect(findSeat(PODCAST, 'seat2')?.id).toBe('seat2');
    expect(findSeat(PODCAST, 'host')?.id).toBe('seat1');
    expect(findSeat(PODCAST, 'guest')?.id).toBe('seat2');
    expect(findSeat(POKER_TABLE, '4')?.id).toBe('seat4');
    expect(findSeat(NEWS_STUDIO, 'co-anchor')?.id).toBe('anchor2');
    expect(findSeat(PODCAST, 'nobody')).toBeUndefined();
  });
  it('poker seats ring the oval, face the centre, seat 4 is open for a human', () => {
    expect(POKER_TABLE.seats).toHaveLength(8);
    for (const s of POKER_TABLE.seats) {
      const fwd = [Math.sin(s.rotation), Math.cos(s.rotation)];
      const toC = [-s.position[0], -s.position[2]];
      const l = Math.hypot(toC[0], toC[1]);
      expect((fwd[0] * toC[0] + fwd[1] * toC[1]) / l).toBeGreaterThan(0.99);
      expect(Math.abs(s.position[0])).toBeLessThan(2.1);
    }
    expect(POKER_TABLE.seats.filter((s) => s.open).map((s) => s.id)).toEqual(['seat4']);
  });
});

describe('seat camera targeting', () => {
  it('close:<seat> sits in front of that seat looking at its head', () => {
    for (const def of [PODCAST, POKER_TABLE, NEWS_STUDIO]) {
      for (const s of def.seats) {
        const shot = resolveCameraCue(def, `close:${s.id}`);
        const head = seatHead(s);
        expect(dist(shot.target, head)).toBeLessThan(0.1);
        expect(dist(shot.position, head)).toBeGreaterThan(0.8);
        expect(dist(shot.position, head)).toBeLessThan(1.3);
        // camera is on the seat's facing side
        const f = [Math.sin(s.rotation), Math.cos(s.rotation)];
        expect((shot.position[0] - head[0]) * f[0] + (shot.position[2] - head[2]) * f[1]).toBeGreaterThan(0.8);
        expect(shot.seats).toEqual([s.id]);
      }
    }
  });
  it('roles work in cues and seat-bound presets follow the seat', () => {
    const a = resolveCameraCue(PODCAST, 'single:host');
    const b = resolveCameraCue(PODCAST, 'single:seat1');
    expect(a.position).toEqual(b.position);
    const p = resolveCameraCue(NEWS_STUDIO, 'anchor2-single');
    expect(dist(p.target, seatHead(NEWS_STUDIO.seats[1]))).toBeLessThan(0.15);
    expect(p.position[2]).toBeGreaterThan(NEWS_STUDIO.seats[1].position[2] + 1.5);
  });
  it('two-shot:a+b frames both heads from the open side', () => {
    const shot = resolveCameraCue(PODCAST, 'two-shot:host+guest');
    const ha = seatHead(PODCAST.seats[0]), hb = seatHead(PODCAST.seats[1]);
    const mid = [(ha[0] + hb[0]) / 2, (ha[1] + hb[1]) / 2, (ha[2] + hb[2]) / 2];
    expect(dist(shot.target, mid)).toBeLessThan(0.2);
    expect(shot.position[2]).toBeGreaterThan(mid[2]);
    expect(shot.seats).toEqual(['seat1', 'seat2']);
    // opposite poker seats (facing each other) still get a valid side-on shot
    const opp = resolveCameraCue(POKER_TABLE, 'two-shot:seat1+seat5');
    expect(Number.isFinite(opp.position[0])).toBe(true);
  });
  it('wide / overhead / orbit and unknown cues', () => {
    expect(resolveCameraCue(NEWS_STUDIO, 'wide').cue).toBe('wide');
    expect(resolveCameraCue(POKER_TABLE, 'overhead').position[1]).toBeGreaterThan(4);
    const o0 = resolveCameraCue(POKER_TABLE, 'orbit', 0), o1 = resolveCameraCue(POKER_TABLE, 'orbit', 5);
    expect(dist(o0.position, o1.position)).toBeGreaterThan(0.5);
    expect(resolveCameraCue(COMEDY_CLUB, 'close').fov).toBe(26);
    expect(() => resolveCameraCue(PODCAST, 'close:seat9')).toThrow();
    expect(() => resolveCameraCue(PODCAST, 'dolly')).toThrow();
    expect(isValidCameraCue(PODCAST, 'auto')).toBe(true);
  });
});

describe('active-speaker auto director', () => {
  it('cuts to the speaker, never strobes, goes wide on silence', () => {
    const d = new ActiveSpeakerDirector({ minCutMs: 1200, idleMs: 4000 });
    expect(d.onLine('seat1', 1000, 2500)).toBe('single:seat1');
    expect(d.onLine('seat2', 1500, 2000)).toBeNull(); // < 1.2 s since last cut
    expect(d.onLine('seat2', 4000, 2000)).toBe('close:seat2');
    expect(d.onLine('seat1', 6100, 1200)).toBe('two-shot:seat2+seat1'); // quick back-and-forth
    expect(d.tick(8000)).toBeNull();
    expect(d.tick(12000)).toBe('wide');
    expect(d.tick(13000)).toBeNull();
  });
});

describe('text mouth', () => {
  it('opens during the line, closes after, picks vowel visemes', () => {
    const dur = estimateLineMs('hello there friend');
    let maxOpen = 0;
    for (let t = 0; t < dur; t += 20) maxOpen = Math.max(maxOpen, textMouth('hello there friend', dur, t).open);
    expect(maxOpen).toBeGreaterThan(0.6);
    expect(textMouth('hello', 1000, 1200).open).toBe(0);
    const s = textMouth('ooo', 1000, 450);
    expect(s.visemes.oh).toBeGreaterThan(0);
  });
});

describe('demo timelines', () => {
  it('news: loads the set, 3 headlines, ticker, ≥2 camera cues', () => {
    const t = newsDemo();
    expect(t[0]).toMatchObject({ type: 'set.load', payload: { setId: 'news-studio' } });
    expect(t.filter((c) => c.type === 'overlay.headline')).toHaveLength(3);
    expect(t.some((c) => c.type === 'overlay.ticker')).toBe(true);
    const cams = new Set(t.filter((c) => c.type === 'set.camera').map((c) => c.payload.cue));
    expect(cams.size).toBeGreaterThanOrEqual(3);
    for (const c of cams) expect(isValidCameraCue(NEWS_STUDIO, String(c))).toBe(true);
    for (let i = 1; i < t.length; i++) expect(t[i].at_ms).toBeGreaterThanOrEqual(t[i - 1].at_ms);
  });
  it('podcast: 3 speakers, auto director on', () => {
    const t = podcastDemo();
    expect(new Set(t.filter((c) => c.type === 'dialogue.line').map((c) => c.payload.seat)).size).toBe(3);
    expect(t.some((c) => c.type === 'set.auto_director' && c.payload.on === true)).toBe(true);
  });
});

import { LocalRoom, memoryStorage } from '../src/live/LocalRoom';
describe('LocalRoom multi-writer (play page + control in separate processes)', () => {
  it('merges an event seen on the wire whose localStorage write has not landed yet', () => {
    const stale = memoryStorage();
    const a = new LocalRoom('ep', stale);
    a.execute('set.load', { setId: 'poker-table' });
    const intent = { seq: 2, type: 'poker.intent', actor: 'system', payload: { seat: 4, action: 'call' }, created_at: new Date().toISOString() };
    const res = a.execute('poker.action', { seat: 4, action: 'call' }, undefined, [intent]);
    expect(res.seq).toBe(3);
    expect(a.log.map((e) => e.seq)).toEqual([1, 2, 3]);
  });
});
