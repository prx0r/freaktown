/**
 * LocalTransport/LocalRoom — the offline EpisodeRoom. Same invariants as
 * the DO: persist-then-broadcast, monotonic seq, idempotent commandId,
 * snapshot+replay on connect, camera gate, stage ACKs as events.
 * Two transports share one storage + node's real BroadcastChannel.
 */
import { afterEach, describe, expect, it } from 'vitest';
import type { ShowEvent } from '@funnier/contracts';
import { LocalTransport } from '../src/live/LocalTransport';
import { LocalRoom, memoryStorage } from '../src/live/LocalRoom';
import { EventConsumer } from '../src/EventConsumer';
import { createMemoryRoomStore } from '../src/ports';

const open: LocalTransport[] = [];
afterEach(() => { for (const t of open.splice(0)) t.disconnect(); });

function pair(ep = `ep-${Math.random().toString(36).slice(2)}`) {
  const storage = memoryStorage();
  const control = new LocalTransport({ storage });
  const stage = new LocalTransport({ storage });
  open.push(control, stage);
  return { ep, storage, control, stage };
}

const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));

describe('LocalRoom', () => {
  it('sequences, persists before returning, and applies the shared reducer', () => {
    const room = new LocalRoom('ep', memoryStorage());
    const a = room.execute('show.start', { title: 't' });
    const b = room.execute('character.enter', { appearanceId: 'x' });
    expect(a.event!.seq).toBe(1);
    expect(b.event!.seq).toBe(2);
    expect(room.log.map((e) => e.type)).toEqual(['show.start', 'character.enter']);
    expect(room.state).toMatchObject({ phase: 'intro', activeAppearanceId: 'x', seq: 2 });
    room.execute('show.pause');
    expect(room.state.isPaused).toBe(true);
    room.execute('show.end');
    expect(room.state.phase).toBe('ended');
  });

  it('is idempotent by commandId', () => {
    const room = new LocalRoom('ep', memoryStorage());
    expect(room.execute('show.start', {}, 'c1').status).toBe('ok');
    expect(room.execute('show.start', {}, 'c1')).toMatchObject({ status: 'already_executed', seq: 1 });
    expect(room.log).toHaveLength(1);
  });

  it('drops unknown cameras (same gate as the DO)', () => {
    const room = new LocalRoom('ep', memoryStorage());
    expect(room.execute('camera.cut', { camera: 'DRONE' }).status).toBe('rejected');
    expect(room.execute('camera.cut', { camera: 'COMIC_CLOSE' }).status).toBe('ok');
    expect(room.log).toHaveLength(1);
  });

  it('replays after a seq', () => {
    const room = new LocalRoom('ep', memoryStorage());
    for (const t of ['a', 'b', 'c']) room.execute(t);
    expect(room.replay(1).map((e) => e.seq)).toEqual([2, 3]);
  });
});

describe('LocalTransport', () => {
  it('control commands reach the stage over BroadcastChannel; stage ACKs come back', async () => {
    const { ep, control, stage } = pair();
    const stageSeen: ShowEvent[] = [];
    const controlSeen: ShowEvent[] = [];
    stage.subscribe({ onEvent: (e) => stageSeen.push(e) });
    control.subscribe({ onEvent: (e) => controlSeen.push(e) });
    await stage.connect(ep, { role: 'stage' });
    await control.connect(ep, { role: 'audience' });
    await tick();
    await control.command('performance.preload', { performance_id: 'p1', set_url: 's', audio_url: 'a' });
    await tick();
    expect(stageSeen.map((e) => e.type)).toEqual(['performance.preload']);
    stage.sendStageAck({ event: 'performance.ready', performance_id: 'p1' });
    await tick();
    expect(controlSeen.map((e) => e.type)).toEqual(['performance.preload', 'performance.ready']);
    expect(controlSeen[1].actor).toBe('stage');
    expect(controlSeen[1].seq).toBe(2);
  });

  it('a late stage gets snapshot + full replay, each seq once', async () => {
    const { ep, control, stage } = pair();
    await control.connect(ep, { role: 'audience' });
    await control.command('show.start');
    await control.command('camera.cut', { camera: 'COMIC_MEDIUM' });
    const store = createMemoryRoomStore();
    const consumer = new EventConsumer({ transport: stage, store });
    const seen: number[] = [];
    consumer.onEvent((e) => seen.push(e.seq));
    await consumer.connect(ep, { role: 'stage' });
    await tick();
    expect(seen).toEqual([1, 2]);
    expect(store.state.phase).toBe('intro');
    expect(store.state.camera).toBe('COMIC_MEDIUM');
    await control.command('show.pause');
    await tick();
    expect(seen).toEqual([1, 2, 3]);
    expect(store.state.isPaused).toBe(true);
  });

  it('audience cannot ACK; reactions only count while a performer is on stage', async () => {
    const { ep, control, stage } = pair();
    const crowd: Array<Record<string, number>> = [];
    await control.connect(ep, { role: 'audience' });
    await stage.connect(ep, { role: 'stage' });
    stage.subscribe({ onCrowd: (c) => crowd.push(c) });
    control.sendStageAck({ event: 'performance.ready' });
    control.sendReaction('laugh');
    await tick();
    expect(control.localRoom!.log).toHaveLength(0);
    expect(crowd).toHaveLength(0);
    await control.command('character.enter', { appearanceId: 'x' });
    control.sendReaction('laugh');
    control.sendReaction('nope');
    await tick();
    expect(crowd.at(-1)).toMatchObject({ laugh_events: 1, unique_laughers: 1 });
  });

  it('reset clears the log and tells every tab', async () => {
    const { ep, control, stage } = pair();
    const snaps: Array<{ seq?: number }> = [];
    await control.connect(ep, { role: 'audience' });
    await stage.connect(ep, { role: 'stage' });
    stage.subscribe({ onSnapshot: (s) => snaps.push(s) });
    await control.command('show.start');
    (control as LocalTransport).reset();
    await tick();
    expect(control.localRoom!.log).toHaveLength(0);
    expect(snaps.at(-1)?.seq).toBe(0);
    const r = await control.command('show.start');
    expect(r.seq).toBe(1);
  });
});
