/** Browser shim for node's `crypto.randomInt` (poker-ts deck shuffle). */
export function randomInt(a: number, b?: number): number {
  const [min, max] = b === undefined ? [0, a] : [a, b];
  const span = max - min;
  const buf = new Uint32Array(1);
  globalThis.crypto.getRandomValues(buf);
  return min + (buf[0] % span);
}
export default { randomInt };
