/**
 * SetsPanel — /control section for sets: set picker, load, demo episodes,
 * seat-aware camera buttons, auto director, poker dealer + human seat link.
 * Still commands only: every action is transport.command(); the poker dealer
 * (PokerShow over poker-ts) runs here and reacts to poker.intent events
 * coming back through the same room.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  EventConsumer, PokerShow, POKER_HUMAN_SEAT, SET_REGISTRY, newsDemo, podcastDemo, pokerDemoIntro, pokerSeats,
  NEWS_CAST, PODCAST_CAST, POKER_CAST, type TimedCommand,
} from '@freaktown/stage-runtime';
import type { CastMemberV1, PokerActionV1 } from '@freaktown/contracts';
import { createTransport, type TransportMode } from '../live/transport';

const FACE_EMOTIONS = ['smile', 'smug', 'deadpan', 'surprised', 'annoyed', 'sad'];

const DEFAULT_CAST: Record<string, CastMemberV1[]> = {
  'comedy-club': [],
  'news-studio': NEWS_CAST,
  podcast: PODCAST_CAST,
  'poker-table': POKER_CAST,
};

export function SetsPanel({ episodeId, mode, authKey }: { episodeId: string; mode: TransportMode; authKey: string }) {
  const transport = useMemo(() => createTransport(mode, { authKey }), [mode, authKey]);
  const sets = SET_REGISTRY.list();
  const [setId, setSetId] = useState('news-studio');
  const [loaded, setLoaded] = useState<string | null>(null);
  const [cam, setCam] = useState('wide');
  const [status, setStatus] = useState('');
  const [auto, setAuto] = useState(true);
  const timers = useRef<number[]>([]);
  const poker = useRef<PokerShow | null>(null);
  const humanName = useRef('Open seat');
  const def = SET_REGISTRY.get(setId)!;
  const [faceSeat, setFaceSeat] = useState('seat1');
  useEffect(() => { setFaceSeat(SET_REGISTRY.get(setId)!.seats[0].id); }, [setId]);
  /** Sends ~2 s of synthetic ARKit-52 frames (what a phone's MediaPipe FaceLandmarker would stream). */
  const puppet = () => {
    for (let i = 0; i < 20; i++) {
      timers.current.push(window.setTimeout(() => {
        const t = i / 20;
        void send('face.blendshapes', { seat: faceSeat, weights: {
          jawOpen: Math.abs(Math.sin(t * Math.PI * 4)) * 0.8, mouthSmileLeft: t, mouthSmileRight: t,
          cheekSquintLeft: t * 0.6, cheekSquintRight: t * 0.6, browInnerUp: 1 - t, eyeBlinkLeft: i % 7 === 0 ? 1 : 0, eyeBlinkRight: i % 7 === 0 ? 1 : 0,
        } });
      }, i * 100));
    }
  };

  const send = (type: string, payload: Record<string, unknown>) => transport.command(type, payload);

  useEffect(() => {
    const consumer = new EventConsumer({ transport });
    const off = consumer.onEvent((e) => {
      const p = e.payload ?? {};
      if (e.type === 'set.load') setLoaded(String(p.setId));
      if (e.type === 'set.camera' && typeof p.cue === 'string') setCam(p.cue);
      if (e.type === 'poker.intent' && poker.current) {
        void poker.current.apply(Number(p.seat), p.action as PokerActionV1, p.amount as number | undefined, 'human')
          .then((er) => { if (er) setStatus(`intent rejected: ${er}`); });
      }
      if (e.type === 'poker.showdown') setStatus('showdown — hand complete');
      if (e.type === 'seat.join' && Number(p.seat) === POKER_HUMAN_SEAT) humanName.current = String(p.name ?? 'Player');
    });
    void consumer.connect(episodeId, { role: 'audience', sessionId: `sets-${Date.now()}` }).catch(() => setStatus('link failed'));
    return () => { off(); consumer.disconnect(); };
  }, [transport, episodeId]);

  useEffect(() => () => { timers.current.forEach(clearTimeout); poker.current?.stop(); }, []);

  const stopAll = () => { timers.current.forEach(clearTimeout); timers.current = []; poker.current?.stop(); poker.current = null; };

  const runTimeline = (tl: TimedCommand[]) => {
    for (const c of tl) timers.current.push(window.setTimeout(() => { void send(c.type, c.payload).catch((e) => setStatus(String(e))); }, c.at_ms));
  };

  const loadSet = async () => { stopAll(); await send('set.load', { setId, cast: DEFAULT_CAST[setId] ?? [] }); setStatus(`loaded ${setId}`); };
  const runDemo = async () => {
    stopAll();
    if (setId === 'news-studio') { runTimeline(newsDemo()); setStatus('news demo running'); }
    else if (setId === 'podcast') { runTimeline(podcastDemo()); setStatus('podcast demo running'); }
    else if (setId === 'poker-table') {
      runTimeline(pokerDemoIntro());
      timers.current.push(window.setTimeout(() => void dealHand(), 2500));
        setStatus(`poker demo: 5 bots + open seat ${POKER_HUMAN_SEAT}`);
    } else await loadSet();
  };
  const dealHand = async () => {
    poker.current?.stop();
    const show = new PokerShow(send, { seats: pokerSeats(humanName.current), humanTimeoutMs: 30000 });
    poker.current = show;
    show.onFinish = () => setStatus('hand finished');
    await show.start();
    setStatus('hand dealt — bots acting, waiting on the human seat when it is their turn');
  };
  const cut = (cue: string) => void send('set.camera', { cue, source: 'human_director' }).then(() => setCam(cue));
  const toggleAuto = () => { const on = !auto; setAuto(on); void send('set.auto_director', { on }); };

  const playHref = `${import.meta.env.BASE_URL}play/${episodeId}/seat/${POKER_HUMAN_SEAT}?transport=${mode}`;
  const seatCues = def.seats.slice(0, 6).map((s) => `close:${s.id}`);

  return (
    <section style={card} data-testid="sets-panel">
      <h2 style={h2}>Set <span style={pill('#333')} data-testid="set-loaded">{loaded ?? 'comedy-club (default)'}</span></h2>
      <div style={row}>
        <select value={setId} onChange={(e) => setSetId(e.target.value)} style={input} data-testid="set-picker">
          {sets.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button style={btn('#2d6cdf')} onClick={() => void loadSet()} data-testid="set-load">Load set</button>
        <button style={btn('#ff2fa0')} onClick={() => void runDemo()} data-testid="set-demo">▶ Run demo</button>
        {setId === 'poker-table' && <button style={btn('#1b8a3a')} onClick={() => void dealHand()} data-testid="poker-deal">Deal hand</button>}
        <button style={btn('#444')} onClick={stopAll}>Stop</button>
      </div>
      <div style={{ fontSize: 12, opacity: 0.75, margin: '6px 0' }}>{def.description} · {def.seats.length} seats</div>
      {setId !== 'comedy-club' && (
        <>
          <div style={row}>
            {def.controlCameras.map((c) => (
              <button key={c} style={btn(cam === c ? '#2d6cdf' : '#333')} onClick={() => cut(c)} data-testid={`setcam-${c}`}>{def.cameras[c]?.label ?? c}</button>
            ))}
            <button style={btn(auto ? '#1f7a3a' : '#333')} onClick={toggleAuto} data-testid="set-auto">Auto: {auto ? 'on' : 'off'}</button>
          </div>
          <div style={{ ...row, marginTop: 6 }}>
            {seatCues.map((c) => <button key={c} style={btn(cam === c ? '#2d6cdf' : '#262130')} onClick={() => cut(c)}>{c}</button>)}
          </div>
        </>
      )}
      {setId !== 'comedy-club' && (
        <div style={{ ...row, marginTop: 6 }} data-testid="face-row">
          <select value={faceSeat} onChange={(e) => setFaceSeat(e.target.value)} style={{ ...input, minWidth: 90, flex: 0 }} data-testid="face-seat">
            {def.seats.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}
          </select>
          {FACE_EMOTIONS.map((e) => (
            <button key={e} style={btn('#3a2a55')} onClick={() => void send('face.expression', { seat: faceSeat, emotion: e, intensity: 1, duration_ms: 2500 })} data-testid={`face-${e}`}>{e}</button>
          ))}
          <button style={btn('#553a2a')} onClick={puppet} data-testid="face-puppet">ARKit puppet test</button>
        </div>
      )}
      {setId === 'poker-table' && (
        <div style={{ fontSize: 13, marginTop: 8 }}>
          Human seat: <a href={playHref} target="_blank" rel="noreferrer" style={{ color: '#9fd8ff' }} data-testid="play-link">{playHref}</a>
        </div>
      )}
      {status && <div style={{ fontSize: 12, marginTop: 6, color: '#ffd27a' }} data-testid="sets-status">{status}</div>}
    </section>
  );
}

const card: React.CSSProperties = { background: '#16131f', border: '1px solid #2a2438', borderRadius: 10, padding: '12px 14px', marginBottom: 12 };
const h2: React.CSSProperties = { margin: '0 0 10px', fontSize: 15, fontWeight: 700, display: 'flex', gap: 10, alignItems: 'center' };
const row: React.CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8 };
const input: React.CSSProperties = { flex: 1, minWidth: 200, background: '#0c0a12', color: '#eee', border: '1px solid #3a3350', borderRadius: 6, padding: '8px 10px', fontSize: 14 };
const btn = (bg: string): React.CSSProperties => ({ background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '8px 12px', fontSize: 13, fontWeight: 600, cursor: 'pointer' });
const pill = (bg: string): React.CSSProperties => ({ background: bg, color: '#fff', borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600 });
