/**
 * EventConsumer unit tests — token URL, explicit-disconnect silence,
 * backoff reconnect on surprise drops, replay idempotency.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { EventConsumer } from './EventConsumer';
import { useShowStore } from '../store/showStore';

interface FakeSocket {
  url: string;
  readyState: number;
  sent: string[];
  closed: boolean;
  onopen: (() => void) | null;
  onmessage: ((ev: { data: string }) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onclose: (() => void) | null;
  send(d: string): void;
  close(): void;
  serverSend(obj: unknown): void;
}

const sockets: FakeSocket[] = [];

class FakeWebSocket {
  static OPEN = 1;
  url: string;
  readyState = 1;
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    sockets.push(this as unknown as FakeSocket);
  }

  send(d: string): void {
    this.sent.push(d);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }

  serverSend(obj: unknown): void {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

function resetStore(): void {
  useShowStore.setState({
    events: [],
    lastSeq: 0,
    phase: 'pre_show',
    isPaused: false,
    scoresRevealed: false,
    judgeScores: [],
    crowd: {
      active_viewers: 0, unique_laughers: 0, laugh_events: 0,
      claps: 0, boos: 0, crickets: 0, groans: 0,
    },
  });
}

beforeEach(() => {
  sockets.length = 0;
  resetStore();
  vi.stubGlobal('WebSocket', FakeWebSocket);
  vi.stubGlobal('window', {
    location: { protocol: 'http:', host: 'test.local' },
    setTimeout,
    clearTimeout,
  });
  vi.stubGlobal('requestAnimationFrame', () => 1);
  vi.stubGlobal('cancelAnimationFrame', () => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('EventConsumer', () => {
  it('builds a stage-token URL', async () => {
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'stage', token: 'tok123', sessionId: 's1' });
    const sock = sockets[0] as unknown as FakeWebSocket;
    sock.onopen?.();
    await p;
    expect(sock.url).toContain('/live/ep1/ws');
    expect(sock.url).toContain('type=stage');
    expect(sock.url).toContain('token=tok123');
    expect(sock.url).toContain('sessionId=s1');
    const ready = JSON.parse(sock.sent[0]);
    expect(ready).toEqual({ type: 'ready', last_seq: 0 });
    c.disconnect();
  });

  it('explicit disconnect never reconnects (no zombies)', async () => {
    vi.useFakeTimers();
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'audience' });
    (sockets[0] as unknown as FakeWebSocket).onopen?.();
    await p;
    expect(sockets).toHaveLength(1);
    c.disconnect();
    await vi.advanceTimersByTimeAsync(30000);
    expect(sockets).toHaveLength(1);
  });

  it('surprise drops reconnect with backoff', async () => {
    vi.useFakeTimers();
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'audience' });
    (sockets[0] as unknown as FakeWebSocket).onopen?.();
    await p;
    // Surprise close (not via disconnect)
    (sockets[0] as unknown as FakeWebSocket).onclose?.();
    expect(sockets).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(sockets).toHaveLength(2);
    c.disconnect();
  });

  it('replayed events apply once (idempotent store)', async () => {
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'stage' });
    const sock = sockets[0] as unknown as FakeWebSocket;
    sock.onopen?.();
    await p;
    const ev = { seq: 5, type: 'show.start', actor: 'system', payload: {}, created_at: new Date().toISOString() };
    sock.serverSend({ type: 'show.event', data: ev });
    sock.serverSend({ type: 'show.event', data: ev }); // duplicate delivery
    expect(useShowStore.getState().events).toHaveLength(1);
    expect(useShowStore.getState().phase).toBe('intro');
    c.disconnect();
  });

  it('reads snake_case snapshots', async () => {
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'stage' });
    const sock = sockets[0] as unknown as FakeWebSocket;
    sock.onopen?.();
    await p;
    sock.serverSend({
      type: 'show.snapshot',
      data: { episode_id: 'ep1', phase: 'judging', active_appearance_id: null, seq: 42, is_paused: false },
    });
    expect(useShowStore.getState().phase).toBe('judging');
    expect(useShowStore.getState().episodeId).toBe('ep1');
    c.disconnect();
  });

  it('auth rejection disconnects silently', async () => {
    vi.useFakeTimers();
    const c = new EventConsumer();
    const p = c.connect('ep1', { role: 'stage', token: 'bad' });
    const sock = sockets[0] as unknown as FakeWebSocket;
    sock.onopen?.();
    await p;
    sock.serverSend({ type: 'auth.rejected', data: { reason: 'invalid token' } });
    await vi.advanceTimersByTimeAsync(30000);
    expect(sockets).toHaveLength(1); // rejected → disconnect() → no reconnect
  });
});
