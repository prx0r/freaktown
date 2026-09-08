/**
 * StagePage — the production stage view (program feed).
 *
 * This is what OBS Browser Source captures: clean, no debug UI.
 * Append ?debug=1 for diagnostics (phase/time/camera overlays).
 *
 * Auth: the stage connects with an episode-scoped HMAC token minted by
 * control (POST /live/:ep/stage-token). Launch as /stage/:ep?token=...
 * Without a token the scene renders but the socket is rejected — the
 * banner says so instead of failing silently.
 *
 * Audio unlock: first user gesture resumes the AudioContext (iPhone).
 * OBS sources with autoplay enabled typically don't need the tap.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { StageRuntime } from '../stage/StageRuntime';
import { StageEventExecutor } from '../stage/StageEventExecutor';
import { useShowStore } from '../store/showStore';

export function StagePage({ episodeId: propEpisodeId }: { episodeId?: string }) {
  const { episodeId: urlEpisodeId } = useParams<{ episodeId: string }>();
  const [search] = useSearchParams();
  const episodeId = propEpisodeId || urlEpisodeId || 'demo';
  const token = search.get('token') ?? undefined;
  const debug = search.get('debug') === '1';

  const containerRef = useRef<HTMLDivElement>(null);
  const [audioLocked, setAudioLocked] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState('EMPTY');

  const phase = useShowStore((s) => s.phase);
  const currentTimeMs = useShowStore((s) => s.currentTimeMs);
  const currentCamera = useShowStore((s) => s.currentCamera);

  const runtimeRef = useRef<StageRuntime | null>(null);
  const executorRef = useRef<StageEventExecutor | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const runtime = new StageRuntime({
      mode: 'live',
      container: containerRef.current,
      background: '#0a0a1a',
    });
    runtimeRef.current = runtime;
    const offStatus = runtime.onStatus((s) => setRuntimeStatus(s));

    // Execution layer: show events → runtime actions. Without this the
    // store updates but the Three.js scene never moves.
    const executor = new StageEventExecutor(runtime, runtime.consumer, {
      onError: (m) => console.error('[stage executor]', m),
    });
    executor.attach();
    executorRef.current = executor;

    runtime
      .connect(episodeId, token)
      .catch(() => setAuthError('stage socket rejected — mint a token from /control'));

    // Audio unlock probe: mobile Safari starts Web Audio suspended; the
    // first PLAY must come from a user gesture, so offer the tap.
    const timer = window.setTimeout(() => {
      if (runtimeRef.current?.isAudioLocked()) setAudioLocked(true);
    }, 1200);
    void timer;

    return () => {
      window.clearTimeout(timer);
      executor.detach();
      executorRef.current = null;
      offStatus();
      runtime.dispose();
      runtimeRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [episodeId]);

  // NOTE: no keyboard handler here. CameraDirector owns keys 1-6
  // (bound inside StageRuntime); a second handler would call
  // cutCamera() with raw key strings and crash.

  const unlockAudio = async () => {
    await runtimeRef.current?.unlockAudio().catch(() => {});
    setAudioLocked(false);
  };

  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div
      style={{
        width: '100vw', height: '100vh', position: 'relative',
        overflow: 'hidden', background: '#000',
      }}
      onPointerDown={() => { if (audioLocked) void unlockAudio(); }}
    >
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}
      />

      {debug && (
        <>
          <div style={debugBox({ top: 20, left: 20 })}>
            <div style={{ opacity: 0.7, marginBottom: 4 }}>PHASE</div>
            <div style={{ fontSize: 18, fontWeight: 'bold' }}>{phase.toUpperCase()}</div>
          </div>
          <div style={debugBox({ top: 20, right: 20 })}>
            <div style={{ opacity: 0.7, marginBottom: 4 }}>TIME</div>
            <div style={{ fontSize: 24, fontWeight: 'bold' }}>{formatTime(currentTimeMs)}</div>
          </div>
          <div style={debugBox({ bottom: 20, right: 20, fontSize: 12 })}>
            CAM: {currentCamera} · {runtimeStatus}
          </div>
        </>
      )}

      {audioLocked && (
        <button
          onClick={unlockAudio}
          style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, -50%)', zIndex: 30,
            background: '#ff00aa', color: '#fff', border: 'none',
            padding: '16px 28px', borderRadius: 8, fontSize: 16, cursor: 'pointer',
          }}
        >
          TAP TO ENABLE AUDIO
        </button>
      )}

      {authError && (
        <div style={{
          position: 'absolute', bottom: 20, left: 20, zIndex: 30,
          color: '#ffb3b3', fontSize: 13, background: 'rgba(0,0,0,0.7)',
          padding: '8px 12px', borderRadius: 4,
        }}>
          {authError}
        </div>
      )}
    </div>
  );
}

function debugBox(pos: Record<string, number | string>): React.CSSProperties {
  return {
    position: 'absolute', color: '#fff', fontSize: 14, fontFamily: 'monospace',
    background: 'rgba(0,0,0,0.6)', padding: '8px 12px', borderRadius: 4, zIndex: 10,
    ...pos,
  };
}
