/** Browser shim for node's `assert` (poker-ts calls assert(cond, msg)). */
function assert(cond: unknown, message?: string): asserts cond {
  if (!cond) throw new Error(message || 'assertion failed');
}
export default assert;
