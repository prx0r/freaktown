/**
 * /tnts — Try-Not-To-Smile vs agents.
 *
 * You sit at the podcast table with agent players (persistent identities).
 * Agents perform bits through the stage; your webcam face is scored on this
 * device (MediaPipe blendshapes → smileFusion → your calibrated neutral) and
 * only the score + game events reach the rules engine. Agent smiles are
 * SIMULATED from each agent's taste model and labelled as such.
 *
 *   /tnts                            camera (asks for webcam permission), calibrate, play
 *   /tnts?feed=recorded&src=<json>   fake webcam: recorded blendshape stream
 *   /tnts?feed=synthetic&grin=6000   fake webcam: neutral, grins from 6 s on
 *   /tnts?spectate=1                 agents only; you watch
 *   ?capture=1                       deterministic: window.__tnts.renderAt(ms) (render CLI)
 *   ?lives=3&hold=400&threshold=0.5&rounds=3&turn=15000&seed=x&agents=pog.a,pog.b
 */
import React, { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import { SetEventExecutor, SetStage, type EventConsumer } from '@funnier/stage-runtime';
import type { ShowEvent } from '@funnier/contracts';
import { TntsGame, calibrateNeutral, smileScore, adjustSmile, type TntsEvent, type TntsConfig, type StageCue } from '@funnier/party';
import { resolveAsset } from '../live/transport';
import { IconBulb, IconHeart, IconLock, IconMic, IconSkull, IconSmile } from '../party/icons';
import { cameraSource, recordedSource, syntheticSource, type FaceSource, type RecordedFeed } from '../party/faceSource';

export const DEFAULT_AGENTS = ['pog.doug-deadline', 'pog.madame-chrysalis', 'pog.the-algorithm'];
const HUMAN = { id: 'you', name: 'You' };
const CALIBRATE_MS = 3000;

interface SeatSnap { id: string; name: string; kind: 'human' | 'agent'; seat: string; lives: number; out: boolean; smile: number; strikes: number; score: number; simulated: boolean; dark: boolean; restingSmiler: boolean }
interface Snap { t: number; phase: string; performer: string | null; round: number; winner: string | null; seats: SeatSnap[]; humanRaw: number; line: { who: string; text: string; seat?: string } | null; events: TntsEvent[] }

declare global {
  interface Window {
    __tnts?: {
      ready: boolean;
      duration_ms: number;
      renderAt: (ms: number) => Promise<void>;
      state: () => TntsGame['state'] | null;
      log: () => TntsEvent[];
      uiPhase: () => string;
    };
  }
}

const nullConsumer = { onEvent: () => () => {} } as unknown as EventConsumer;

function snapOf(g: TntsGame, t: number, humanRaw: number, line: Snap['line']): Snap {
  const s = g.state;
  return {
    t, phase: s.phase, performer: s.performer, round: s.round, winner: s.winner, humanRaw, line,
    seats: s.order.map((id) => { const p = s.players[id]; return { id, name: p.name, kind: p.kind, seat: p.seat, lives: p.lives, out: p.out, smile: p.smile, strikes: p.strikes, score: p.score, simulated: p.simulated, dark: p.dark, restingSmiler: p.restingSmiler }; }),
    events: g.log.filter((e) => e.t > t - 2600 && e.t <= t),
  };
}

function synthLevel(grinAt: number) {
  return (rel: number) => (rel >= grinAt ? 0.9 : 0.04 + 0.02 * Math.sin(rel / 300));
}

export function TntsPage() {
  const [q] = useSearchParams();
  const capture = q.get('capture') === '1';
  const spectate = q.get('spectate') === '1';
  const feedKind = (q.get('feed') ?? 'camera') as 'camera' | 'recorded' | 'synthetic';
  const autostart = q.get('autostart') === '1' || capture || feedKind !== 'camera';
  const seed = q.get('seed') ?? 'tnts-demo';
  const agents = (q.get('agents') ?? DEFAULT_AGENTS.join(',')).split(',').filter(Boolean);
  const num = (k: string) => (q.get(k) !== null ? Number(q.get(k)) : undefined);
  const config: Partial<TntsConfig> = Object.fromEntries(Object.entries({ lives: num('lives'), holdMs: num('hold'), smileThreshold: num('threshold'), rounds: num('rounds'), turnMs: num('turn') }).filter(([, v]) => v !== undefined));

  const stageRef = useRef<HTMLDivElement>(null);
  const tileRef = useRef<HTMLDivElement>(null);
  const faceCanvas = useRef<HTMLCanvasElement>(null);
  const [snap, setSnap] = useState<Snap | null>(null);
  const [ui, setUi] = useState<'setup' | 'calibrating' | 'ready' | 'playing' | 'over'>(spectate ? 'playing' : 'setup');
  const uiRef = useRef(ui);
  uiRef.current = ui;
  const [calibMsg, setCalibMsg] = useState('');
  const [camStatus, setCamStatus] = useState('');
  const [lighting, setLighting] = useState<'ok' | 'dark'>('ok');
  const engine = useRef<{ game: TntsGame; source: FaceSource | null; t0: number; calib: number[]; calibStart: number; start: () => void; punch: () => void; useSource: (s: FaceSource) => void } | null>(null);

  useEffect(() => {
    if (!stageRef.current) return;
    const stage = new SetStage({ container: stageRef.current, quality: q.get('quality') === 'low' ? 'low' : 'high', manual: true, resolveUrl: resolveAsset });
    const executor = new SetEventExecutor(stage, nullConsumer, { onError: (m) => console.warn('[tnts]', m) });
    const game = new TntsGame({ seed, agents, config });
    const humans = spectate ? [] : [HUMAN];
    let lastLine: Snap['line'] = null;
    let chain: Promise<void> = Promise.resolve();
    let seq = 0;
    const exec = (c: StageCue) => {
      if (c.type === 'dialogue.line') {
        const seat = String(c.payload.seat);
        const p = Object.values(game.state.players).find((x) => x.seat === seat);
        lastLine = { who: p?.name ?? seat, text: String(c.payload.text), seat };
      }
      chain = chain.then(async () => {
        stage.advanceClock(c.t);
        await executor.execute({ seq: ++seq, type: c.type, actor: 'tnts', payload: c.payload } as ShowEvent);
      }).catch((e) => console.warn('[tnts] cue failed', e));
    };

    let raf: number | null = null;
    const api: NonNullable<Window['__tnts']> = { ready: false, duration_ms: 0, renderAt: async () => {}, state: () => game.state, log: () => game.log, uiPhase: () => uiRef.current };
    window.__tnts = api;

    if (capture) {
      // ── deterministic: simulate the whole game, then render any t ──
      const grin = Number(q.get('grin') ?? 42000);
      const feedP: Promise<FaceSource | null> = spectate ? Promise.resolve(null)
        : q.get('src') ? fetch(q.get('src')!).then((r) => r.json()).then((f: RecordedFeed) => recordedSource(f, 0))
          : Promise.resolve(syntheticSource(synthLevel(grin), 0));
      void feedP.then(async (src) => {
        game.seat(humans, 0);
        const snaps: Snap[] = [];
        const calib: number[] = [];
        let line: Snap['line'] = null;
        const cueIdx = { i: 0 };
        let raw = 0;
        const until = Number(q.get('until') ?? 240000);
        if (spectate) game.start(0);
        for (let t = 0; t <= until; t += 50) {
          const fr = src?.sample(t) ?? null;
          raw = fr?.bs ? smileScore(fr.bs) : 0;
          if (src && game.state.phase === 'lobby') {
            calib.push(raw);
            if (t >= CALIBRATE_MS) { const c = calibrateNeutral(calib); game.calibrated(HUMAN.id, c.baseline, c.restingSmiler, t); game.start(t); }
          } else if (src && game.state.phase === 'turn' && !game.state.players[HUMAN.id]?.out) {
            if (fr) game.lighting(HUMAN.id, fr.luma, t);
            game.humanSmile(HUMAN.id, raw, t);
          }
          if (game.state.phase === 'turn' && game.state.performer === HUMAN.id) { if (t - game.state.turnStartedAt >= 4000) game.humanPunchline(t); }
          game.update(t);
          while (cueIdx.i < game.cues.length && game.cues[cueIdx.i].t <= t) {
            const c = game.cues[cueIdx.i++];
            if (c.type === 'dialogue.line') { const p = Object.values(game.state.players).find((x) => x.seat === c.payload.seat); line = { who: p?.name ?? '', text: String(c.payload.text), seat: String(c.payload.seat) }; }
          }
          if (t % 100 === 0) snaps.push(snapOf(game, t, raw, line));
          if (game.state.phase === 'over' && snaps.length && t > (game.log.at(-1)?.t ?? 0) + 4000) break;
        }
        const cues = [...game.cues].sort((a, b) => a.t - b.t);
        let ci = 0; let last = -1;
        api.duration_ms = snaps.at(-1)?.t ?? 0;
        api.renderAt = async (ms: number) => {
          if (ms < last) { ci = 0; }
          while (ci < cues.length && cues[ci].t <= ms) {
            const c = cues[ci++];
            if (c.type === 'dialogue.line' && c.t + Number(c.payload.duration_ms ?? 0) < ms - 200) continue;
            stage.advanceClock(c.t);
            await executor.execute({ seq: ci, type: c.type, actor: 'tnts', payload: c.payload } as ShowEvent);
          }
          last = ms;
          stage.renderAt(ms);
          const s = snaps[Math.min(snaps.length - 1, Math.max(0, Math.floor(ms / 100)))];
          flushSync(() => { setSnap(s); setUi(s.phase === 'over' ? 'over' : s.phase === 'lobby' ? 'calibrating' : 'playing'); });
        };
        await api.renderAt(0);
        api.ready = true;
      });
      return () => { stage.dispose(); if (window.__tnts === api) delete window.__tnts; };
    }

    // ── realtime ──
    const t0 = performance.now();
    game.seat(humans, 0);
    const eng = {
      game, source: null as FaceSource | null, t0, calib: [] as number[], calibStart: 0,
      start: () => { const r = game.start(performance.now() - t0); if (r.some((e) => e.type === 'game.started')) setUi('playing'); },
      punch: () => game.humanPunchline(performance.now() - t0),
      useSource: (s: FaceSource) => { eng.source = s; eng.calib = []; eng.calibStart = performance.now(); setUi('calibrating'); setCalibMsg('Hold a neutral face…'); },
    };
    engine.current = eng;
    if (spectate) game.start(0);
    else if (feedKind === 'recorded' && q.get('src')) fetch(q.get('src')!).then((r) => r.json()).then((f: RecordedFeed) => eng.useSource(recordedSource(f, performance.now())));
    else if (feedKind === 'synthetic') eng.useSource(syntheticSource(synthLevel(Number(q.get('grin') ?? 1e9)), performance.now()));

    let lastSnap = 0, lastLum = 0, raw = 0;
    const loop = () => {
      const now = performance.now();
      const t = now - t0;
      const src = eng.source;
      const fr = src?.sample(now) ?? null;
      if (fr?.bs) raw = smileScore(fr.bs);
      if (src && uiRef.current === 'calibrating') {
        if (fr?.bs) eng.calib.push(raw);
        if (now - eng.calibStart >= CALIBRATE_MS) {
          const c = calibrateNeutral(eng.calib);
          if (c.ok) {
            game.calibrated(HUMAN.id, c.baseline, c.restingSmiler, t);
            setCalibMsg(c.restingSmiler ? `Calibrated. Your resting face reads ${c.baseline} — we score you relative to it (fairness).` : `Calibrated (neutral ${c.baseline}).`);
            setUi('ready');
            uiRef.current = 'ready';
            if (autostart) eng.start();
          } else {
            setCalibMsg(c.reason === 'too-few-samples' ? 'No face found — face the camera, light in front of you.' : c.reason === 'too-noisy' ? 'Too much movement — hold still and neutral.' : 'That was a smile! Neutral face please.');
            eng.calib = []; eng.calibStart = now;
          }
        }
      }
      if (src && fr && game.state.phase === 'turn' && game.state.players[HUMAN.id] && !game.state.players[HUMAN.id].out) {
        if (now - lastLum > 500) { lastLum = now; game.lighting(HUMAN.id, fr.luma, t); setLighting(game.state.players[HUMAN.id].dark ? 'dark' : 'ok'); }
        if (fr.bs) game.humanSmile(HUMAN.id, raw, t);
      }
      game.update(t);
      while (execIdx < game.cues.length) exec(game.cues[execIdx++]);
      stage.renderAt(t);
      if (now - lastSnap > 100) {
        lastSnap = now;
        const s = snapOf(game, t, raw, lastLine);
        setSnap(s);
        if (s.phase === 'over' && uiRef.current !== 'over') setUi('over');
      }
      raf = requestAnimationFrame(loop);
    };
    // every cue (seat(), start(), punch(), update()) goes through one cursor
    let execIdx = 0;
    api.ready = true;
    raf = requestAnimationFrame(loop);
    return () => { if (raf !== null) cancelAnimationFrame(raf); eng.source?.stop(); stage.dispose(); if (window.__tnts === api) delete window.__tnts; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capture, spectate, feedKind, seed]);

  // human tile: the real camera video (mirrored), or a drawn face for fake feeds
  useEffect(() => {
    const v = engine.current?.source?.video;
    if (v && tileRef.current && !tileRef.current.contains(v)) {
      Object.assign(v.style, { width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', borderRadius: '8px' });
      tileRef.current.prepend(v);
    }
  });
  useEffect(() => {
    const c = faceCanvas.current;
    if (!c || !snap) return;
    const g = c.getContext('2d')!;
    const w = c.width, h = c.height, s = Math.min(1, snap.humanRaw);
    g.fillStyle = '#1b1d2a'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#e9c39b'; g.beginPath(); g.ellipse(w / 2, h / 2 + 4, w * 0.3, h * 0.36, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#222';
    const eyeH = 5 * (1 - 0.6 * s);
    g.beginPath(); g.ellipse(w / 2 - 16, h / 2 - 8, 5, eyeH, 0, 0, Math.PI * 2); g.ellipse(w / 2 + 16, h / 2 - 8, 5, eyeH, 0, 0, Math.PI * 2); g.fill();
    g.strokeStyle = '#7a2b2b'; g.lineWidth = 4; g.beginPath();
    g.moveTo(w / 2 - 18, h / 2 + 22); g.quadraticCurveTo(w / 2, h / 2 + 22 + 26 * s - 4, w / 2 + 18, h / 2 + 22); g.stroke();
  }, [snap]);

  const startCamera = async () => {
    try { const s = await cameraSource(setCamStatus); engine.current?.useSource(s); setCamStatus(s.status); }
    catch (e) { setCamStatus(`camera unavailable: ${e instanceof Error ? e.message : String(e)} — try ?feed=synthetic or watch`); }
  };

  const perf = snap?.seats.find((x) => x.id === snap.performer);
  const human = snap?.seats.find((x) => x.id === HUMAN.id);
  const humanTurn = snap?.performer === HUMAN.id && snap.phase === 'turn';
  const winner = snap?.seats.find((x) => x.id === snap.winner);
  const toast = snap?.events.filter((e) => e.type === 'smile.break' || e.type === 'player.out' || e.type === 'fairness.resting_smiler').at(-1);
  const nameOf = (id: string | null | undefined) => snap?.seats.find((x) => x.id === id)?.name ?? id ?? '';
  const showFace = feedKind !== 'camera' || capture;

  return (
    <div data-testid="tnts-room" className="tnts" style={{ position: 'relative', width: '100vw', height: '100dvh', overflow: 'hidden', background: '#07060a', color: '#f3f1ec', fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif" }}>
      <style>{CSS}</style>
      <div ref={stageRef} className="tnts-stage" />
      <header className="tnts-top">
        <div className="tnts-brand">FUNNIER · <b>TRY NOT TO SMILE</b></div>
        <div data-testid="tnts-status" className="tnts-status">
          {snap?.phase === 'turn' ? <>Round {snap.round} · <b>{perf?.name}</b> is performing</> : snap?.phase === 'over' ? 'Game over' : ui === 'calibrating' ? 'Calibrating' : 'Lobby'}
        </div>
      </header>

      {snap?.line && snap.phase === 'turn' && snap.line.seat === perf?.seat && (
        <div data-testid="tnts-caption" className="tnts-caption"><b>{snap.line.who}:</b> {snap.line.text}</div>
      )}
      <div className="tnts-notices" data-testid="tnts-notices">
        {toast && (
          <div data-testid="tnts-toast" className="tnts-toast">
            {toast.type === 'smile.break' && <><IconSmile /> <b>{toast.id === HUMAN.id ? 'You' : nameOf(toast.id)}</b> cracked{toast.by ? <> at {toast.by === HUMAN.id ? 'your' : `${nameOf(toast.by)}'s`} bit</> : null} · {toast.lives} {toast.lives === 1 ? 'life' : 'lives'} left{toast.simulated ? ' (simulated)' : ''}</>}
            {toast.type === 'player.out' && (toast.id === HUMAN.id ? <><IconSkull /> <b>You're out</b>: spectating now</> : <><IconSkull /> <b>{nameOf(toast.id)}</b> is out</>)}
            {toast.type === 'fairness.resting_smiler' && <>Resting smiler detected: scoring relative to your neutral face</>}
          </div>
        )}
        {human?.out && snap?.phase === 'turn' && !(toast?.type === 'player.out' && toast.id === HUMAN.id) && <div className="tnts-spect" data-testid="tnts-spectating">You're out: spectating</div>}
        {lighting === 'dark' && <div data-testid="tnts-lighting" className="tnts-warn"><IconBulb /> Too dark to read your face — judging paused. Face a light.</div>}
      </div>

      <section className="tnts-seats" data-testid="tnts-seats">
        {(snap?.seats ?? []).map((p) => (
          <div key={p.id} data-testid={`seat-${p.kind === 'human' ? 'human' : p.seat}`} className={`tnts-seat ${p.out ? 'out' : ''} ${snap?.performer === p.id ? 'on' : ''} ${p.kind}`}>
            {p.kind === 'human' ? (
              <div className="tnts-tile" ref={tileRef}>
                {showFace && <canvas ref={faceCanvas} width={120} height={96} className="tnts-face" />}
                {!showFace && !engine.current?.source && <div className="tnts-nocam">camera off</div>}
                <div className="tnts-priv"><IconLock size={9} /> <span className="long">video stays on this device · only scores leave</span><span className="short">on-device</span></div>
              </div>
            ) : (
              <div className="tnts-avatar">{p.name.split(' ').map((w) => w[0]).join('').slice(0, 2)}</div>
            )}
            <div className="tnts-meta">
              <div className="tnts-name" title={p.name}>{p.name}{snap?.performer === p.id ? <> <IconMic className="tnts-mic" /></> : ''}</div>
              <div className="tnts-lives" aria-label={`${p.lives} lives`}>{p.out ? 'OUT' : Array.from({ length: Math.max(0, p.lives) }, (_, i) => <IconHeart key={i} />)}<span className="pts"> · {p.score} pts</span></div>
              <div className="tnts-meter"><i style={{ width: `${Math.round(p.smile * 100)}%`, background: p.smile > 0.5 ? '#ff2fa8' : '#F5C86B' }} /><em style={{ left: `${(snapThreshold(config) * 100).toFixed(0)}%` }} /></div>
              <div className="tnts-src">{p.kind === 'agent' ? 'smile: simulated (taste model)' : p.restingSmiler ? 'smile: measured · resting-smile adjusted' : showFace ? `smile: measured (${capture ? (q.get('src') ? 'recorded' : 'synthetic') : feedKind} feed)` : 'smile: measured on-device'}</div>
            </div>
          </div>
        ))}
      </section>

      {!capture && !spectate && ui === 'setup' && (
        <div className="tnts-modal" data-testid="tnts-setup">
          <h2>Try Not To Smile</h2>
          <p>Agents take turns telling you jokes. Smile for longer than {((config.holdMs ?? 400) / 1000).toFixed(1)}s and you lose a life. Your face is read <b>on this device</b>; no video is sent anywhere.</p>
          <div className="row">
            <button data-testid="tnts-camera" onClick={() => void startCamera()}>Use my camera</button>
            <a className="btn ghost" href={`?spectate=1`}>Just watch</a>
          </div>
          {camStatus && <p className="small">{camStatus}</p>}
        </div>
      )}
      {!capture && ui === 'calibrating' && (
        <div className="tnts-modal small" data-testid="tnts-calibrating"><h3>Calibrating</h3><p>{calibMsg || 'Hold a neutral face for 3 seconds.'}</p><p className="small">{camStatus}</p></div>
      )}
      {!capture && ui === 'ready' && (
        <div className="tnts-modal small" data-testid="tnts-ready"><p>{calibMsg}</p><button data-testid="tnts-start" onClick={() => engine.current?.start()}>Start game</button></div>
      )}
      {!capture && humanTurn && !human?.out && (
        <div className="tnts-yourturn" data-testid="tnts-yourturn">Your turn: tell the table a joke, then <button data-testid="tnts-punch" onClick={() => engine.current?.punch()}>PUNCHLINE!</button></div>
      )}
      {snap?.phase === 'over' && (
        <div className="tnts-modal small" data-testid="tnts-over">
          <h2>{winner ? `${winner.name} wins` : 'Draw'}</h2>
          {human?.out && <p>You cracked. You're spectating now.</p>}
          {!capture && <button onClick={() => window.location.reload()}>Play again</button>}
        </div>
      )}
      <footer className="tnts-rules">Smile above {snapThreshold(config)} for {((config.holdMs ?? 400) / 1000).toFixed(1)}s = lose a life · agent smiles are simulated from their taste · your face is read on this device</footer>
    </div>
  );
}

function snapThreshold(c: Partial<TntsConfig>) { return c.smileThreshold ?? 0.5; }
// keep adjustSmile in the bundle for consumers that compute meters client-side
void adjustSmile;

const CSS = `
.tnts-stage{position:absolute;inset:0}
.tnts-top{position:absolute;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:center;padding:10px 16px;z-index:5;background:linear-gradient(#000a,#0000)}
.tnts-brand{font-size:13px;letter-spacing:2px;color:#ff2fa8}
.tnts-brand b{color:#fff}
.tnts-status{font-size:14px}
.tnts-caption{position:absolute;left:50%;bottom:190px;transform:translateX(-50%);max-width:min(92%,900px);text-align:center;font-size:clamp(14px,2vw,22px);background:#0008;padding:6px 14px;border-radius:6px;z-index:6;text-shadow:0 2px 6px #000}
.tnts-caption b{color:#F5C86B}
.tnts-notices{position:absolute;top:52px;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;align-items:center;gap:6px;z-index:7;pointer-events:none;max-width:92vw}
.tnts-toast{background:#ff2fa8;color:#fff;padding:8px 16px;border-radius:20px;font-size:15px;white-space:nowrap;box-shadow:0 4px 14px #0008}
.tnts-toast .ic{width:1.25em;height:1.25em}
.tnts-warn{background:#ffd28a;color:#222;padding:6px 12px;border-radius:6px}
.tnts-spect{background:#2a2836;padding:4px 10px;border-radius:6px;font-size:12px}
.tnts-seats{position:absolute;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;padding:10px 14px 14px;z-index:6;background:linear-gradient(#0000,#000c 30%)}
.tnts-seat{display:flex;gap:10px;align-items:center;background:#14131cdd;border:1px solid #2a2836;border-radius:10px;padding:8px;min-width:0}
.tnts-seat.on{border-color:#F5C86B;box-shadow:0 0 0 2px #F5C86B55}
.tnts-seat.out{opacity:.45;filter:grayscale(1)}
.tnts-seat.human{border-color:#7BDFF2}
.tnts-avatar{flex:none;width:64px;height:64px;border-radius:50%;background:#2a2836;display:grid;place-items:center;font-weight:800;font-size:20px;color:#F5C86B}
.tnts-tile{flex:none;position:relative;width:120px;height:96px;border-radius:8px;overflow:hidden;background:#000}
.tnts-face{width:100%;height:100%;display:block}
.tnts-nocam{position:absolute;inset:0;display:grid;place-items:center;font-size:11px;color:#888}
.tnts-priv{position:absolute;left:0;right:0;bottom:0;font-size:8.5px;line-height:1.2;background:#000a;padding:2px 4px;color:#cfe}
.tnts-meta{min-width:0;flex:1}
.tnts-rules{display:none}
.tnts-priv .short{display:none}
.tnts-name{font-weight:700;font-size:14px;line-height:1.2;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tnts-name .tnts-mic{color:#F5C86B}
.tnts-lives{color:#ff2fa8;font-size:13px;display:flex;align-items:center;gap:2px;flex-wrap:wrap}
.tnts-lives .pts{color:#aaa}
.tnts-meter{position:relative;height:7px;background:#2a2836;border-radius:4px;margin:5px 0 3px;overflow:visible}
.tnts-meter i{display:block;height:100%;border-radius:4px;transition:width .1s}
.tnts-meter em{position:absolute;top:-3px;width:2px;height:13px;background:#fff8}
.tnts-src{font-size:10.5px;color:#9a98a8;line-height:1.25}
.tnts-modal{position:absolute;left:50%;top:44%;transform:translate(-50%,-50%);background:#14131cf2;border:1px solid #2a2836;border-radius:14px;padding:20px 24px;z-index:9;width:min(460px,90vw);text-align:center}
.tnts-modal.small{width:min(380px,88vw)}
.tnts-modal h2{margin:0 0 8px;color:#F5C86B}
.tnts-modal .row{display:flex;gap:10px;justify-content:center;margin-top:12px}
.tnts-modal .small,.tnts-modal p.small{font-size:12px;color:#aaa}
.tnts button,.tnts .btn{background:#ff2fa8;color:#fff;border:0;border-radius:8px;padding:9px 16px;font-weight:700;font-size:14px;cursor:pointer;text-decoration:none}
.tnts .btn.ghost{background:transparent;border:1px solid #555}
.tnts-yourturn{position:absolute;left:50%;bottom:200px;transform:translateX(-50%);background:#14131cf2;padding:10px 16px;border-radius:10px;z-index:8;display:flex;gap:10px;align-items:center;white-space:nowrap}
@media (max-width:760px){
  /* phone: stage on top (62%), seat grid fills the rest above the rules line */
  .tnts-stage{bottom:auto;height:62%}
  .tnts-seats{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:1fr;gap:8px;padding:8px 10px;top:62%;bottom:52px;background:#07060a}
  .tnts-seat{padding:10px 8px;gap:9px;align-items:center}
  .tnts-avatar{width:52px;height:52px;font-size:17px}
  .tnts-tile{width:66px;height:66px}
  .tnts-priv .long{display:none}
  .tnts-priv .short{display:inline}
  .tnts-name{font-size:15px}
  .tnts-lives{font-size:14px}
  .tnts-src{font-size:10.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .tnts-caption{bottom:calc(38% + 10px);font-size:15px;width:92%;background:#0c0b12d9}
  .tnts-yourturn{bottom:60px;white-space:normal;width:90vw}
  .tnts-notices{top:66px;width:92vw}
  .tnts-toast{white-space:normal;text-align:center;font-size:13px;padding:7px 14px}
  .tnts-top{flex-direction:column;align-items:flex-start;gap:2px;padding:8px 10px}
  .tnts-rules{display:block;position:absolute;left:12px;right:12px;bottom:10px;font-size:11px;color:#8a8898;text-align:center;line-height:1.35}
}
`;
