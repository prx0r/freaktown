/** Seeded PRNG (mulberry32) + string hashing. Every agent decision draws from one of these, so a game is a pure function of (seed, inputs). */

export type Rng = () => number;

export function hashString(s: string): number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

export function mulberry32(seed: number | string): Rng {
  let a = (typeof seed === 'string' ? hashString(seed) : seed) >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const pick = <T>(rng: Rng, xs: readonly T[]): T => xs[Math.floor(rng() * xs.length) % xs.length];
export const clamp01 = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);
export const sigmoid = (x: number): number => 1 / (1 + Math.exp(-x));
export const round3 = (x: number): number => Math.round(x * 1000) / 1000;
