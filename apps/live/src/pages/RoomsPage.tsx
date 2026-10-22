/**
 * /rooms — lobby of always-on rooms (podcast, poker, TNTS, newsroom) with agent residents.
 * /rooms/:roomId — watch a room on its set; take a seat / leave.
 *
 * Talks to the local rooms server (npm run party:rooms → :8791; ?server=<url> to override).
 * If no server answers, the rooms run in this tab instead (same RoomRuntime, banner says so).
 * In the TNTS room a seated human's face is scored on-device; only the score is POSTed.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { SetEventExecutor, SetStage, type EventConsumer } from '@funnier/stage-runtime';
import type { ShowEvent } from '@funnier/contracts';
import { createRooms, smileScore, type RoomEvent, type RoomRuntime, type SeatInfo } from '@funnier/party';
import { resolveAsset } from '../live/transport';
import { cameraSource, syntheticSource, type FaceSource } from '../party/faceSource';

interface LobbyRoom { id: string; kind: string; title: string; blurb: string; setId: string; seats: SeatInfo[]; last: string | null }

let LOCAL: Map<string, RoomRuntime> | null = null;
let LOCAL_T0 = 0;
let LOCAL_TIMER: ReturnType<typeof setInterval> | null = null;
function localRooms(): Map<string, RoomRuntime> {
  if (!LOCAL) {
    LOCAL = createRooms();
    LOCAL_T0 = performance.now();
    LOCAL_TIMER = setInterval(() => { const t = performance.now() - LOCAL_T0; for (const r of LOCAL!.values()) r.advance(t); }, 100);
  }
  return LOCAL;
}
void LOCAL_TIMER;

const serverOf = (q: URLSearchParams) => q.get('server') ?? `http://${window.location.hostname || '127.0.0.1'}:8791`;
const nullConsumer = { onEvent: () => () => {} } as unknown as EventConsumer;

export function RoomsPage() {
  const { roomId } = useParams();
  return roomId ? <RoomView id={roomId} /> : <Lobby />;
}

function Lobby() {
  const [q] = useSearchParams();
  const [rooms, setRooms] = useState<LobbyRoom[]>([]);
  const [mode, setMode] = useState<'server' | 'local' | 'loading'>('loading');
  useEffect(() => {
    let dead = false;
    const load = async () => {
      try {
        if (q.get('local') === '1') throw new Error('local');
        const r = await fetch(`${serverOf(q)}/rooms`, { signal: AbortSignal.timeout(1500) });
        const j = await r.json();
        if (!dead) { setRooms(j.rooms); setMode('server'); }
      } catch {
        const rs = localRooms();
        if (!dead) {
          setMode('local');
          setRooms([...rs.values()].map((r) => { const l = [...r.events].reverse().find((e) => e.type === 'dialogue.line'); return { id: r.def.id, kind: r.def.kind, title: r.def.title, blurb: r.def.blurb, setId: r.def.setId, seats: r.seats(), last: l ? String(l.payload.text) : null }; }));
        }
      }
    };
    void load();
    const iv = setInterval(load, 2500);
    return () => { dead = true; clearInterval(iv); };
  }, []);
  const qs = q.toString() ? `?${q.toString()}` : '';
  return (
    <div data-testid="rooms-lobby" style={{ minHeight: '100dvh', background: '#07060a', color: '#f3f1ec', fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif", padding: '24px clamp(14px,4vw,48px)' }}>
      <div style={{ fontSize: 13, letterSpacing: 2, color: '#ff2fa8' }}>FUNNIER · ALWAYS ON</div>
      <h1 style={{ margin: '6px 0 4px' }}>Rooms</h1>
      <p style={{ color: '#9a98a8', marginTop: 0 }}>Agent residents keep these rooms running around the clock. Watch, or take a seat.</p>
      <div data-testid="rooms-mode" style={{ fontSize: 12, color: mode === 'server' ? '#7BDFF2' : '#ffd28a', marginBottom: 14 }}>
        {mode === 'server' ? `connected to rooms server ${serverOf(q)}` : mode === 'local' ? 'no rooms server: rooms are running in this tab (npm run party:rooms for shared rooms)' : 'connecting…'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))', gap: 14 }}>
        {rooms.map((r) => (
          <div key={r.id} data-testid={`room-card-${r.id}`} style={{ background: '#14131c', border: '1px solid #2a2836', borderRadius: 12, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <b style={{ fontSize: 17 }}>{r.title}</b>
              <span style={{ fontSize: 11, color: '#ff2fa8' }}>● LIVE</span>
            </div>
            <p style={{ color: '#9a98a8', fontSize: 13, margin: '6px 0 10px' }}>{r.blurb}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {r.seats.map((s) => <span key={s.seat} style={{ fontSize: 11.5, padding: '3px 8px', borderRadius: 12, background: s.kind === 'human' ? '#1d3b44' : s.kind === 'resident' ? '#2a2836' : 'transparent', border: s.kind === 'empty' ? '1px dashed #444' : '1px solid transparent', color: s.kind === 'empty' ? '#777' : '#ddd' }}>{s.name ?? 'open seat'}</span>)}
            </div>
            <div style={{ fontSize: 12.5, color: '#cfcde0', minHeight: 34, fontStyle: 'italic' }}>{r.last ? `“${r.last}”` : '…'}</div>
            <Link data-testid={`room-open-${r.id}`} to={`/rooms/${r.id}${qs}`} style={{ display: 'inline-block', marginTop: 10, background: '#ff2fa8', color: '#fff', borderRadius: 8, padding: '8px 14px', fontWeight: 700, textDecoration: 'none', fontSize: 14 }}>Enter</Link>
          </div>
        ))}
      </div>
    </div>
  );
}

function RoomView({ id }: { id: string }) {
  const [q] = useSearchParams();
  const ref = useRef<HTMLDivElement>(null);
  const [seats, setSeats] = useState<SeatInfo[]>([]);
  const [line, setLine] = useState<{ who: string; text: string } | null>(null);
  const [mode, setMode] = useState<'server' | 'local' | 'loading'>('loading');
  const [me, setMe] = useState<{ token?: string; id: string; seat: string | null; waiting: boolean } | null>(null);
  const [name, setName] = useState('Guest');
  const nameRef = useRef(name);
  nameRef.current = name;
  const [note, setNote] = useState('');
  const api = useRef<{ join: () => Promise<void>; leave: () => Promise<void> } | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const stage = new SetStage({ container: ref.current, quality: q.get('quality') === 'low' ? 'low' : 'high', manual: true, resolveUrl: resolveAsset });
    const exec = new SetEventExecutor(stage, nullConsumer, { onError: (m) => console.warn('[room]', m) });
    let base: number | null = null;
    const roomNow = () => (base === null ? 0 : performance.now() - base);
    let chain: Promise<void> = Promise.resolve();
    let seq = 0;
    const seatName = new Map<string, string>();
    const handle = (e: RoomEvent & { snapshot?: boolean }) => {
      if (base === null) base = performance.now() - e.t;
      if (e.type === 'set.load' || e.type === 'set.cast') {
        for (const c of (e.payload.cast as Array<{ seat: string; name: string }>) ?? []) seatName.set(c.seat, c.name);
      }
      if (e.type === 'dialogue.line') setLine({ who: seatName.get(String(e.payload.seat)) ?? String(e.payload.seat), text: String(e.payload.text) });
      if (e.type === 'room.seat' || e.type === 'room.leave' || e.type === 'room.queue') setNote(e.type === 'room.seat' ? `${e.payload.name} took ${e.payload.seat}${e.payload.yielded_by ? ` (${e.payload.yielded_by} stepped aside)` : ''}` : e.type === 'room.queue' ? `${e.payload.name} ${e.payload.note}` : `${e.payload.name} left`);
      if (e.type.startsWith('room.') || e.type.startsWith('tnts.')) return;
      chain = chain.then(async () => {
        stage.advanceClock(Math.max(e.t, roomNow()));
        await exec.execute({ seq: ++seq, type: e.type, actor: 'room', payload: e.payload } as ShowEvent);
      }).catch(() => {});
    };
    let raf: number | null = null;
    const loop = () => { stage.renderAt(roomNow()); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);

    let es: EventSource | null = null;
    let off: (() => void) | null = null;
    let seatTimer: ReturnType<typeof setInterval> | null = null;
    let face: FaceSource | null = null;
    let faceTimer: ReturnType<typeof setInterval> | null = null;
    const server = serverOf(q);
    const startLocal = () => {
      const r = localRooms().get(id);
      if (!r) { setNote('no such room'); return; }
      setMode('local');
      for (const e of r.snapshot(performance.now() - LOCAL_T0)) handle(e);
      off = r.on(handle);
      seatTimer = setInterval(() => setSeats(r.seats()), 500);
      setSeats(r.seats());
      api.current = {
        join: async () => { const res = r.join('me', nameRef.current, performance.now() - LOCAL_T0); setMe({ id: 'me', seat: res.seat, waiting: res.waiting }); },
        leave: async () => { r.leave('me', performance.now() - LOCAL_T0); setMe(null); },
      };
    };
    const startScores = (send: (raw: number) => void) => {
      // TNTS room: score the face here, send only the number
      const feed = q.get('feed');
      const go = (s: FaceSource) => { face = s; faceTimer = setInterval(() => { const f = s.sample(performance.now()); if (f?.bs) send(smileScore(f.bs)); }, 100); };
      if (feed === 'synthetic') go(syntheticSource(() => 0.05, performance.now()));
      else cameraSource(() => {}).then(go).catch(() => setNote('camera unavailable: watching only'));
    };
    if (q.get('local') === '1') startLocal();
    else {
      fetch(`${server}/rooms`, { signal: AbortSignal.timeout(1500) }).then((r) => r.json()).then(() => {
        setMode('server');
        es = new EventSource(`${server}/rooms/${id}/events`);
        es.onmessage = (m) => handle(JSON.parse(m.data));
        const poll = () => fetch(`${server}/rooms`).then((r) => r.json()).then((j) => setSeats(j.rooms.find((x: LobbyRoom) => x.id === id)?.seats ?? [])).catch(() => {});
        void poll();
        seatTimer = setInterval(poll, 1500);
        api.current = {
          join: async () => {
            const j = await (await fetch(`${server}/rooms/${id}/join`, { method: 'POST', body: JSON.stringify({ name: nameRef.current }) })).json();
            if (!j.ok) { setNote(j.error ?? 'could not join'); return; }
            setMe({ token: j.token, id: j.id, seat: j.seat, waiting: j.waiting });
            if (id === 'tnts') startScores((raw) => void fetch(`${server}/rooms/${id}/input`, { method: 'POST', body: JSON.stringify({ token: j.token, kind: 'smile', raw }) }));
          },
          leave: async () => {
            setMe((m) => { if (m?.token) void fetch(`${server}/rooms/${id}/leave`, { method: 'POST', body: JSON.stringify({ token: m.token }) }); return null; });
            face?.stop(); if (faceTimer) clearInterval(faceTimer);
          },
        };
      }).catch(startLocal);
    }
    return () => { if (raf !== null) cancelAnimationFrame(raf); es?.close(); off?.(); if (seatTimer) clearInterval(seatTimer); if (faceTimer) clearInterval(faceTimer); face?.stop(); stage.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <div data-testid="room-view" className="rv" style={{ position: 'relative', width: '100vw', height: '100dvh', overflow: 'hidden', background: '#07060a', color: '#f3f1ec', fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif" }}>
      <style>{ROOM_CSS}</style>
      <div ref={ref} className="rv-stage" />
      <div style={{ position: 'absolute', top: 10, left: 14, right: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 5, gap: 8, flexWrap: 'wrap' }}>
        <Link to={`/rooms${q.toString() ? `?${q}` : ''}`} style={{ color: '#ff2fa8', textDecoration: 'none', fontSize: 13, letterSpacing: 2 }}>← ROOMS</Link>
        <span data-testid="room-mode" style={{ fontSize: 11.5, color: mode === 'server' ? '#7BDFF2' : '#ffd28a' }}>● LIVE · {id} · {mode === 'server' ? 'rooms server' : mode === 'local' ? 'running in this tab' : '…'}</span>
      </div>
      {line && <div data-testid="room-caption" className="rv-caption"><b style={{ color: '#F5C86B' }}>{line.who}:</b> {line.text}</div>}
      <div className="rv-bar">
        <div className="rv-seats">
          {seats.map((s) => <span key={s.seat} data-testid={`room-seat-${s.seat}`} className={`rv-chip ${s.kind}`}>{s.name ?? 'open seat'}{s.kind === 'resident' ? <em>resident</em> : s.kind === 'human' ? <em>human</em> : ''}</span>)}
        </div>
        <div className="rv-actions">
        {!me ? (
          <>
            <input data-testid="room-name" aria-label="your name" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 110, minWidth: 0, flex: '0 1 110px', background: '#14131c', color: '#fff', border: '1px solid #333', borderRadius: 6, padding: '7px 8px' }} />
            <button data-testid="room-join" onClick={() => void api.current?.join()} style={{ background: '#ff2fa8', color: '#fff', border: 0, borderRadius: 8, padding: '8px 14px', fontWeight: 700 }}>{id === 'tnts' ? 'Join next game' : 'Take a seat'}</button>
          </>
        ) : (
          <>
            <span data-testid="room-me" className="rv-me">{me.waiting ? 'queued for the next game (only your smile score is sent)' : `you are in ${me.seat}`}</span>
            <button data-testid="room-leave" onClick={() => void api.current?.leave()} style={{ background: 'transparent', color: '#fff', border: '1px solid #555', borderRadius: 8, padding: '8px 14px' }}>Leave</button>
          </>
        )}
        </div>
      </div>
      {note && <div data-testid="room-note" className="rv-note">{note}</div>}
    </div>
  );
}

const ROOM_CSS = `
.rv-stage{position:absolute;inset:0}
.rv-caption{position:absolute;left:50%;bottom:110px;transform:translateX(-50%);max-width:min(92%,900px);text-align:center;font-size:clamp(14px,2vw,21px);background:#0009;padding:6px 14px;border-radius:6px;z-index:6}
.rv-bar{position:absolute;left:0;right:0;bottom:0;padding:10px 14px 14px;display:flex;gap:8px;align-items:center;z-index:6;background:linear-gradient(#0000,#000c 35%)}
.rv-seats{display:flex;gap:8px;flex-wrap:wrap;flex:1;min-width:0}
.rv-actions{display:flex;gap:8px;align-items:center;flex:none}
.rv-chip{font-size:12px;padding:4px 9px;border-radius:12px;border:1px solid transparent;white-space:nowrap}
.rv-chip.resident{background:#2a2836}
.rv-chip.human{background:#1d3b44}
.rv-chip.empty{border:1px dashed #555;color:#999}
.rv-chip em{font-style:normal;color:#9a98a8}
.rv-chip em::before{content:' · '}
.rv-me{font-size:13px}
.rv-note{position:absolute;top:40px;left:50%;transform:translateX(-50%);background:#14131cee;padding:5px 12px;border-radius:14px;font-size:12.5px;z-index:7;max-width:92vw;text-align:center}
@media (max-width:760px){
  /* phone: stage on top, a solid panel below holds the caption, seats and the join controls */
  .rv{display:flex;flex-direction:column}
  .rv-stage{position:relative;inset:auto;flex:1 1 auto;min-height:0}
  .rv-caption{position:static;transform:none;max-width:none;margin:0;border-radius:0;background:#14131c;font-size:15px;padding:10px 14px;border-top:1px solid #2a2836}
  .rv-bar{position:static;flex:none;flex-direction:column;align-items:stretch;background:#07060a;padding:10px 12px 16px;gap:10px}
  .rv-seats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
  .rv-chip{font-size:12.5px;padding:6px 10px;white-space:normal;overflow-wrap:anywhere;border-radius:8px}
  .rv-chip em{display:block;font-size:10.5px}
  .rv-chip em::before{content:none}
  .rv-actions{justify-content:stretch}
  .rv-actions input{flex:1 1 auto !important;width:auto !important}
  .rv-actions button{flex:none}
  .rv-me{flex:1}
  .rv-note{top:36px}
}
`;
