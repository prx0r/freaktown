/**
 * Always-on rooms server (local dev). No deps beyond node:http.
 *
 *   npx vite-node packages/party/server/rooms-server.ts          # :8791   (npm run party:rooms)
 *   ROOMS_PORT=8791 ROOMS_TICK_MS=100
 *
 *   GET  /rooms                         lobby: rooms, residents, seats, now playing
 *   GET  /rooms/:id/events?since=seq    SSE: snapshot (set.load) + replay since seq + live tail
 *   POST /rooms/:id/join   {name}       → {token, seat | waiting}
 *   POST /rooms/:id/leave  {token}
 *   POST /rooms/:id/input  {token, kind:'smile'|'calibrated', raw}   (TNTS: a SCORE, never video)
 *
 * Transport: plain SSE + POST (the same shape as party.py and EpisodeRoom).
 * LiveKit (livekit_adapter.py) is the media plane when a server is configured
 * on the box; it is not needed for rooms to run, and not used locally.
 */
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { createRooms, type RoomRuntime } from '../src/rooms';

export interface RoomsServer { server: http.Server; rooms: Map<string, RoomRuntime>; stop: () => void; url: string }

export async function startRoomsServer(port = Number(process.env.ROOMS_PORT ?? 8791), tickMs = Number(process.env.ROOMS_TICK_MS ?? 100)): Promise<RoomsServer> {
  const rooms = createRooms();
  const t0 = Date.now();
  const now = () => Date.now() - t0;
  const tokens = new Map<string, { room: string; id: string }>();
  const timer = setInterval(() => { const t = now(); for (const r of rooms.values()) r.advance(t); }, tickMs);

  const json = (res: http.ServerResponse, code: number, body: unknown) => {
    res.writeHead(code, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(body));
  };
  const readBody = (req: http.IncomingMessage) => new Promise<Record<string, unknown>>((resolve) => {
    let s = '';
    req.on('data', (c) => { s += c; if (s.length > 10_000) req.destroy(); });
    req.on('end', () => { try { resolve(s ? JSON.parse(s) : {}); } catch { resolve({}); } });
  });

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://x');
    const parts = url.pathname.split('/').filter(Boolean);
    if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST' }); res.end(); return; }
    if (parts[0] !== 'rooms') return json(res, 404, { ok: false, error: 'not found' });
    if (parts.length === 1) {
      return json(res, 200, {
        ok: true, t: now(), transport: 'sse', livekit: !!process.env.LIVEKIT_URL,
        rooms: [...rooms.values()].map((r) => ({ id: r.def.id, kind: r.def.kind, title: r.def.title, blurb: r.def.blurb, setId: r.def.setId, seats: r.seats(), last: r.events.at(-1)?.type === 'dialogue.line' ? r.events.at(-1)!.payload.text : null })),
      });
    }
    const room = rooms.get(parts[1]);
    if (!room) return json(res, 404, { ok: false, error: 'no such room' });
    if (parts[2] === 'events' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive', 'Access-Control-Allow-Origin': '*' });
      const send = (e: unknown) => res.write(`data: ${JSON.stringify(e)}\n\n`);
      const since = Number(url.searchParams.get('since') ?? 0);
      for (const e of room.snapshot(now())) send({ ...e, snapshot: true });
      for (const e of room.since(since)) if (e.t > now() - 8000) send(e);
      const off = room.on(send);
      const ping = setInterval(() => res.write(': ping\n\n'), 15000);
      req.on('close', () => { off(); clearInterval(ping); });
      return;
    }
    if (req.method !== 'POST') return json(res, 405, { ok: false });
    const body = await readBody(req);
    if (parts[2] === 'join') {
      const id = `human.${randomBytes(4).toString('hex')}`;
      const name = String(body.name ?? 'Guest').slice(0, 24) || 'Guest';
      const r = room.join(id, name, now());
      if (!r.ok) return json(res, 409, r);
      const token = randomBytes(12).toString('hex');
      tokens.set(token, { room: room.def.id, id });
      return json(res, 200, { ...r, token, id });
    }
    const who = tokens.get(String(body.token ?? ''));
    if (!who || who.room !== room.def.id) return json(res, 403, { ok: false, error: 'bad token' });
    if (parts[2] === 'leave') { tokens.delete(String(body.token)); return json(res, 200, { ok: room.leave(who.id, now()) }); }
    if (parts[2] === 'input') return json(res, 200, { ok: room.input(who.id, body as { kind: string; raw?: number }, now()) });
    return json(res, 404, { ok: false });
  });
  await new Promise<void>((r) => server.listen(port, '127.0.0.1', r));
  const addr = server.address();
  const url = `http://127.0.0.1:${typeof addr === 'object' && addr ? addr.port : port}`;
  return { server, rooms, url, stop: () => { clearInterval(timer); server.close(); } };
}

// run directly: vite-node packages/party/server/rooms-server.ts
// (vite-node does not put the script in argv; anything but vitest importing this module means "run")
if (!process.env.VITEST && !process.env.ROOMS_NO_MAIN) {
  startRoomsServer().then((s) => console.log(`FUNNIER rooms always-on at ${s.url}/rooms (${[...s.rooms.keys()].join(', ')})`));
}
