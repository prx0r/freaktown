/**
 * Transport unit tests — clock math with an injected fake AudioContext.
 * play → advance → pause → resume → seek → end, all deterministic.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { Transport } from './Transport';

interface FakeSource {
  buffer: unknown;
  connectedTo: unknown;
  startedAt: [number, number] | null;
  stopped: boolean;
  onended: (() => void) | null;
  connect(dest: unknown): void;
  start(when: number, offset: number): void;
  stop(): void;
}

interface FakeContext {
  currentTime: number;
  state: string;
  destination: object;
  sources: FakeSource[];
  resumeCalls: number;
  resume(): Promise<void>;
  createBufferSource(): FakeSource;
  decodeAudioData(): Promise<{ duration: number }>;
}

function makeFakeContext(): FakeContext {
  const ctx: FakeContext = {
    currentTime: 100,
    state: 'running',
    destination: {},
    sources: [],
    resumeCalls: 0,
    async resume() { this.resumeCalls += 1; ctx.state = 'running'; },
    createBufferSource() {
      const src: FakeSource = {
        buffer: null,
        connectedTo: null,
        startedAt: null,
        stopped: false,
        onended: null,
        connect(dest: unknown) { this.connectedTo = dest; },
        start(when: number, offset: number) { this.startedAt = [when, offset]; },
        stop() { this.stopped = true; },
      };
      ctx.sources.push(src);
      return src;
    },
    async decodeAudioData() { return { duration: 10 }; },
  };
  return ctx;
}

beforeEach(() => {
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => 1 as unknown as number);
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Transport', () => {
  it('plays, advances with the context clock, pauses frozen, resumes', async () => {
    const t = new Transport();
    const ctx = makeFakeContext();
    t.setAudioContext(ctx as unknown as AudioContext);
    await t.loadAudioFromBytes(new ArrayBuffer(8));

    t.play();
    expect(t.state).toBe('playing');

    ctx.currentTime = 102; // +2s of media
    expect(t.currentTimeMs).toBeCloseTo(2000, 0);

    t.pause();
    expect(t.state).toBe('paused');
    ctx.currentTime = 120; // wall clock moves, media frozen
    expect(t.currentTimeMs).toBeCloseTo(2000, 0);

    t.resume();
    expect(t.state).toBe('playing');
    ctx.currentTime = 121; // +1s after resume
    expect(t.currentTimeMs).toBeCloseTo(3000, 0);
  });

  it('seeks and ends', async () => {
    const t = new Transport();
    const ctx = makeFakeContext();
    t.setAudioContext(ctx as unknown as AudioContext);
    await t.loadAudioFromBytes(new ArrayBuffer(8));

    t.play();
    t.seek(5000);
    expect(t.currentTimeMs).toBeCloseTo(5000, 0);

    // Simulate natural end of the buffer source
    const src = ctx.sources[ctx.sources.length - 1];
    src.onended?.();
    expect(t.state).toBe('ended');
  });

  it('routes voice into the provided output node, not destination', async () => {
    const t = new Transport();
    const ctx = makeFakeContext();
    t.setAudioContext(ctx as unknown as AudioContext);
    const bus = { id: 'voice-bus' };
    t.setOutputNode(bus as unknown as AudioNode);
    await t.loadAudioFromBytes(new ArrayBuffer(8));
    t.play();
    expect(ctx.sources[0].connectedTo).toBe(bus);
  });

  it('play is a no-op without loaded audio', () => {
    const t = new Transport();
    t.setAudioContext(makeFakeContext() as unknown as AudioContext);
    t.play();
    expect(t.state).toBe('idle');
  });
});
