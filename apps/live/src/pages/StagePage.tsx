/**
 * StagePage — the production stage view (program feed).
 *
 * What OBS Browser Source captures: clean picture, optional captions.
 *   ?transport=local|room   which LiveTransport (default local)
 *   ?token=…                EpisodeRoom stage token (room mode)
 *   ?debug=1                telemetry overlay (phase/time/camera/mouth)
 *   ?captions=0             hide the caption strip
 *   ?capture=1              frame-stepped capture mode (offline MP4), no audio
 *   ?quality=low            half-res, no shadows (software GL / weak devices)
 *   ?cpuskin=1              CPU skinning/morphs (GPUs without vertex texture fetch, CI)
 *
 * The stage obeys events only: StageEventExecutor turns room events into
 * runtime calls. Nothing in /control can reach this page except through
 * the room.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { EventConsumer, SET_REGISTRY, StageEventExecutor, StageRuntime, type StageTelemetry } from '@funnier/stage-runtime';
import { SetStagePage } from './SetStagePage';
import { showClockSink, showRoomStore, useShowStore } from '../store/showStore';
import { createTransport, resolveAsset, transportMode } from '../live/transport';

declare global {
  interface Window {
    __stage?: {
      runtime: StageRuntime;
      executor: StageEventExecutor;
      telemetry: () => StageTelemetry;
      errors: string[];
    };
  }
}

/**
 * StagePage — picks the renderer from the room: the latest `set.load` decides.
 * No set (or comedy-club) → the classic single-performer StageRuntime;
 * any other registered set → SetStagePage (multi-seat).
 */
export function StagePage() {
  const { episodeId = 'demo' } = useParams<{ episodeId: string }>();
  const [search] = useSearchParams();
  const mode = transportMode(search);
  const token = search.get('token') ?? undefined;
  const [setId, setSetId] = useState<string | null>(search.get('set'));
  useEffect(() => {
    const consumer = new EventConsumer({ transport: createTransport(mode) });
    const off = consumer.onEvent((e) => { if (e.type === 'set.load' && typeof e.payload?.setId === 'string') setSetId(e.payload.setId); });
    const offSnap = consumer.onSnapshot((s) => { if (s.seq === 0) setSetId(search.get('set')); });
    void consumer.connect(episodeId, { role: 'audience', sessionId: `stage-router-${Date.now()}`, token }).catch(() => {});
    return () => { off(); offSnap(); consumer.disconnect(); };
  }, [episodeId, mode, token]);
  if (setId && setId !== 'comedy-club' && SET_REGISTRY.has(setId)) {
    return (
      <SetStagePage key={`${episodeId}`} episodeId={episodeId} mode={mode} token={token}
        debug={search.get('debug') === '1'} quality={search.get('quality') === 'low' ? 'low' : 'high'}
        cpuSkinning={search.get('cpuskin') === '1'} glb={search.get('setglb') === '1'} />
    );
  }
  return <ClubStagePage />;
}

export function ClubStagePage() {
  const { episodeId = 'demo' } = useParams<{ episodeId: string }>();
  const [search] = useSearchParams();
  const token = search.get('token') ?? undefined;
  const debug = search.get('debug') === '1';
  const captions = search.get('captions') !== '0';
  const capture = search.get('capture') === '1';
  const quality = search.get('quality') === 'low' ? 'low' : 'high';
  const cpuSkinning = search.get('cpuskin') === '1';
  const mode = transportMode(search);

  const containerRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<StageRuntime | null>(null);
  const [audioLocked, setAudioLocked] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [tele, setTele] = useState<StageTelemetry | null>(null);

  const phase = useShowStore((s) => s.phase);

  useEffect(() => {
    if (!containerRef.current) return;
    const transport = createTransport(mode);
    const errors: string[] = [];
    const runtime = new StageRuntime({
      container: containerRef.current,
      transport,
      store: showRoomStore,
      clockSink: showClockSink,
      keyboard: debug,
      capture,
      quality,
      cpuSkinning,
    });
    runtimeRef.current = runtime;
    const executor = new StageEventExecutor(runtime, runtime.consumer, {
      resolveUrl: resolveAsset,
      onError: (m) => { errors.push(m); console.warn('[stage executor]', m); },
    });
    executor.attach();
    window.__stage = { runtime, executor, telemetry: () => runtime.telemetry(), errors };

    runtime.consumer.transport.subscribe({
      onRejected: (r) => setLinkError(`stage link rejected (${r}) — mint a stage link from /control`),
    });
    runtime.connect(episodeId, token).catch(() =>
      setLinkError(mode === 'room' ? 'EpisodeRoom unreachable — is `wrangler dev` running?' : 'local link failed'));

    const lockTimer = window.setTimeout(() => {
      if (runtimeRef.current?.isAudioLocked()) setAudioLocked(true);
    }, 800);
    const teleTimer = window.setInterval(() => {
      const t = runtime.telemetry();
      setTele(t);
      if (t.status === 'PLAYING' && runtime.isAudioLocked()) setAudioLocked(true);
    }, 200);

    return () => {
      window.clearTimeout(lockTimer);
      window.clearInterval(teleTimer);
      executor.detach();
      runtime.dispose();
      runtimeRef.current = null;
      if (window.__stage?.runtime === runtime) delete window.__stage;
    };
  }, [episodeId, token, mode, debug, capture, quality, cpuSkinning]);

  const unlockAudio = async () => {
    await runtimeRef.current?.unlockAudio().catch(() => {});
    setAudioLocked(false);
  };

  const plan = runtimeRef.current?.currentPlan ?? null;
  const words = plan?.word_timings ?? [];
  const caption = (() => {
    if (!tele || tele.status !== 'PLAYING' || tele.wordIndex < 0 || !words.length) return null;
    const w = words[tele.wordIndex];
    const beatWords = words.filter((x) => x.beat_id === w.beat_id);
    const i = beatWords.indexOf(w);
    const start = Math.max(0, i - 5);
    return beatWords.slice(start, start + 11).map((x) => ({ text: x.word, on: x === w }));
  })();
  const showNameCard = tele && (tele.status === 'PLAYING' || tele.status === 'READY') && tele.timeMs < 5000 && plan;

  return (
    <div
      data-testid="stage"
      style={{ width: '100vw', height: '100dvh', position: 'relative', overflow: 'hidden', background: '#000' }}
      onPointerDown={() => { if (audioLocked) void unlockAudio(); }}
    >
      <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

      {showNameCard && !capture && (
        <div style={nameCard}>
          <div style={{ fontSize: 12, letterSpacing: 3, opacity: 0.75 }}>NOW ON STAGE</div>
          <div style={{ fontSize: 'clamp(18px, 3vw, 30px)', fontWeight: 800 }}>
            {(plan?.character_id ?? '').replace(/^pog\./, '').replace(/-/g, ' ').toUpperCase()}
          </div>
          {plan?.title && <div style={{ fontSize: 13, opacity: 0.8 }}>{plan.title}</div>}
        </div>
      )}

      {captions && caption && (
        <div style={captionStrip} data-testid="caption">
          {caption.map((c, i) => (
            <span key={i} style={{ color: c.on ? '#ffe14d' : '#fff', opacity: c.on ? 1 : 0.85 }}>{c.text} </span>
          ))}
        </div>
      )}

      {debug && tele && (
        <div style={debugBox} data-testid="stage-debug">
          <div>{mode.toUpperCase()} · {phase} · {tele.status} · {tele.audioState}</div>
          <div>t {(tele.timeMs / 1000).toFixed(2)}s / {(tele.durationMs / 1000).toFixed(1)}s · {tele.fps} fps</div>
          <div>cam {tele.camera} · cuts {tele.cuts.length}</div>
          <div>mouth {tele.mouth.toFixed(2)} ({tele.mouthSource}) · blink {tele.blink.toFixed(2)}</div>
          <div>avatar {tele.avatar?.kind}:{tele.avatar?.name} mouth={tele.avatar?.mouthMode}</div>
          <div>face {Object.entries(tele.emotions).filter(([, v]) => v > 0.02).map(([k, v]) => `${k}:${v.toFixed(2)}`).join(' ') || 'neutral'}</div>
        </div>
      )}

      {audioLocked && !capture && (
        <button onClick={unlockAudio} style={unlockBtn}>TAP TO ENABLE AUDIO</button>
      )}

      {linkError && <div style={errorBox}>{linkError}</div>}
    </div>
  );
}

const nameCard: React.CSSProperties = {
  position: 'absolute', left: '4%', bottom: '18%', zIndex: 10, color: '#fff',
  fontFamily: 'Inter, system-ui, sans-serif', padding: '10px 18px',
  background: 'linear-gradient(90deg, rgba(255,47,160,0.85), rgba(80,20,120,0.55))',
  borderLeft: '4px solid #ffe14d', maxWidth: '80%',
};
const captionStrip: React.CSSProperties = {
  position: 'absolute', left: '50%', bottom: '5%', transform: 'translateX(-50%)', zIndex: 10,
  maxWidth: '86%', textAlign: 'center', fontFamily: 'Inter, system-ui, sans-serif',
  fontSize: 'clamp(15px, 2.2vw, 26px)', fontWeight: 700, lineHeight: 1.3,
  background: 'rgba(0,0,0,0.55)', padding: '6px 14px', borderRadius: 6,
};
const debugBox: React.CSSProperties = {
  position: 'absolute', top: 12, left: 12, zIndex: 20, color: '#9fffb0', fontSize: 12,
  fontFamily: 'ui-monospace, monospace', background: 'rgba(0,0,0,0.65)', padding: '8px 10px', borderRadius: 4,
  lineHeight: 1.5,
};
const unlockBtn: React.CSSProperties = {
  position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 30,
  background: '#ff2fa0', color: '#fff', border: 'none', padding: '16px 28px', borderRadius: 8,
  fontSize: 16, fontWeight: 700, cursor: 'pointer',
};
const errorBox: React.CSSProperties = {
  position: 'absolute', bottom: 12, right: 12, zIndex: 30, color: '#ffb3b3', fontSize: 13,
  background: 'rgba(0,0,0,0.75)', padding: '8px 12px', borderRadius: 4, fontFamily: 'system-ui',
};
