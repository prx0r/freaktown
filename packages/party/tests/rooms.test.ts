import { afterAll, describe, expect, it } from 'vitest';
import { RoomRuntime, DEFAULT_ROOMS, createRooms } from '../src/rooms';
import { startRoomsServer, type RoomsServer } from '../server/rooms-server';

const def = (id: string) => DEFAULT_ROOMS.find((d) => d.id === id)!;
const run = (r: RoomRuntime, until: number, step = 100) => { for (let t = 0; t <= until; t += step) r.advance(t); };

describe('always-on rooms (residents keep them running)', () => {
  it('every default room produces events with nobody watching', () => {
    const rooms = createRooms();
    for (const r of rooms.values()) run(r, 60_000);
    const by = Object.fromEntries([...rooms].map(([id, r]) => [id, r.events.map((e) => e.type)]));
    expect(by.podcast).toContain('dialogue.line');
    expect(by.newsroom).toContain('overlay.headline');
    expect(by.poker).toContain('poker.deal');
    expect(by.poker).toContain('poker.action');
    expect(by.tnts).toContain('tnts.turn.started');
    expect(by.tnts).toContain('dialogue.line');
  });

  it('a human takes a free seat or a resident yields; leaving gives it back', () => {
    const r = new RoomRuntime(def('podcast'));
    run(r, 2000);
    const j = r.join('h1', 'Ana', 2000);
    expect(j).toMatchObject({ ok: true, seat: 'seat4' }); // seat4 was empty
    const k = r.join('h2', 'Bo', 2100);
    expect(k.ok).toBe(true);
    expect(r.events.find((e) => e.type === 'room.seat' && e.payload.id === 'h2')?.payload.yielded_by).toBeTruthy();
    expect(r.seats().filter((s) => s.kind === 'human')).toHaveLength(2);
    r.leave('h2', 3000);
    expect(r.seats().filter((s) => s.kind === 'resident')).toHaveLength(3);
    expect(r.join('h1', 'Ana', 3100).ok).toBe(false);
  });

  it('TNTS room: humans queue for the next game and send scores only', () => {
    const r = new RoomRuntime(def('tnts'));
    run(r, 3000);
    const j = r.join('h1', 'Ana', 3000);
    expect(j).toMatchObject({ ok: true, waiting: true });
    // run until the residents' game ends and the next one seats the human
    for (let t = 3000; t < 900_000 && !r.events.some((e) => e.type === 'tnts.game' && (e.payload.players as string[]).includes('h1')); t += 100) r.advance(t);
    expect(r.events.some((e) => e.type === 'tnts.game' && (e.payload.players as string[]).includes('h1'))).toBe(true);
    expect(r.input('h1', { kind: 'smile', raw: 0.1 }, r.events.at(-1)!.t)).toBe(true);
    expect(r.input('h1', { kind: 'video' }, 0)).toBe(false);
  });
});

describe('rooms server (local dev, SSE + POST)', () => {
  let s: RoomsServer;
  afterAll(() => s?.stop());
  it('lists rooms, streams a snapshot + events, joins and leaves a seat', async () => {
    s = await startRoomsServer(0, 50);
    const lobby = await (await fetch(`${s.url}/rooms`)).json();
    expect(lobby.rooms.map((r: { id: string }) => r.id)).toEqual(['podcast', 'poker', 'tnts', 'newsroom']);
    const join = await (await fetch(`${s.url}/rooms/podcast/join`, { method: 'POST', body: JSON.stringify({ name: 'Ana' }) })).json();
    expect(join).toMatchObject({ ok: true, seat: 'seat4' });
    const ctl = new AbortController();
    const res = await fetch(`${s.url}/rooms/podcast/events`, { signal: ctl.signal });
    const reader = res.body!.getReader();
    const { value } = await reader.read();
    const first = JSON.parse(new TextDecoder().decode(value).split('\n')[0].slice(6));
    expect(first).toMatchObject({ type: 'set.load', snapshot: true });
    expect((first.payload.cast as Array<{ name: string }>).some((c) => c.name === 'Ana')).toBe(true);
    ctl.abort();
    const bad = await fetch(`${s.url}/rooms/podcast/leave`, { method: 'POST', body: JSON.stringify({ token: 'nope' }) });
    expect(bad.status).toBe(403);
    const left = await (await fetch(`${s.url}/rooms/podcast/leave`, { method: 'POST', body: JSON.stringify({ token: join.token }) })).json();
    expect(left.ok).toBe(true);
  });
});
