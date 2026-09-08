/**
 * ThreeWsStagePage — killella's three.ws-driven stage.
 *
 * Same show, different renderer than the VRM StagePage:
 * - Avatar: <agent-3d> (idle/clips/gestures/gaze, live say() dialogue)
 * - Set audio: pre-generated recording via <audio> (exact timing owned
 *   by the compositor, same as freaktown's Black Room pattern)
 * - Captions: manifest word timings
 * - Beat cues: gesture/camera/sfx fired at beat starts derived from words
 * - Live events: EpisodeRoom socket (stage.speak → say, verdict → wave)
 *
 * URL: /stage-ws/:episodeId?act=<act_version_id>&avatar=<glb_url>
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ThreeWsAvatar, type ThreeWsAvatarHandle } from '../threews/ThreeWsAvatar';
import { EventConsumer } from '../stage/EventConsumer';
import { useShowStore } from '../store/showStore';

interface ManifestWord { word: string; start_ms: number; end_ms: number }
interface ManifestBeat { id: string; type: string; text: string; gesture?: string; camera?: string; sound?: string }
interface ManifestCue { at: string; beat_id: string; type: string; value: string }
interface PerformanceManifest {
  version: string;
  performance_id: string;
  actor: { name: string; species: string; premise: string; avatar_url: string };
  audio: { set_url: string; duration_ms: number };
  delivery: { beats: ManifestBeat[] };
  words: ManifestWord[];
  motion: { cues: ManifestCue[] };
}

interface BeatWindow { beat_id: string; start_ms: number; end_ms: number; beat: ManifestBeat }

function beatsToWindows(beats: ManifestBeat[], words: ManifestWord[]): BeatWindow[] {
  // Words are emitted in beat order; consume per-beat word counts.
  const windows: BeatWindow[] = [];
  let cursor = 0;
  for (const beat of beats) {
    const count = beat.text.split(/\s+/).filter(Boolean).length;
    const slice = words.slice(cursor, cursor + count);
    cursor += count;
    if (!slice.length) continue;
    windows.push({
      beat_id: beat.id,
      start_ms: slice[0].start_ms,
      end_ms: slice[slice.length - 1].end_ms,
      beat,
    });
  }
  return windows;
}

function resolveAudioUrl(setUrl: string, actId: string): string {
  if (!setUrl) return '';
  if (setUrl.startsWith('acts/')) return `/v1/performances/${actId}/audio`;
  if (setUrl.startsWith('http')) return setUrl;
  return setUrl;
}

export function ThreeWsStagePage() {
  const { episodeId } = useParams<{ episodeId: string }>();
  const [search] = useSearchParams();
  const actId = search.get('act') ?? '';
  const avatarOverride = search.get('avatar') ?? '';

  const avatarRef = useRef<ThreeWsAvatarHandle>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const consumerRef = useRef<EventConsumer | null>(null);
  const firedBeatsRef = useRef<Set<string>>(new Set());

  const [manifest, setManifest] = useState<PerformanceManifest | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [timeMs, setTimeMs] = useState(0);
  const [caption, setCaption] = useState('');

  const phase = useShowStore((s) => s.phase);
  const events = useShowStore((s) => s.events);

  const avatarUrl = avatarOverride || manifest?.actor.avatar_url || undefined;
  const performerName = manifest?.actor.name ?? 'Guest Freak';

  const audioUrl = useMemo(
    () => (manifest && actId ? resolveAudioUrl(manifest.audio.set_url, actId) : ''),
    [manifest, actId]
  );

  const beatWindows = useMemo(
    () => (manifest ? beatsToWindows(manifest.delivery.beats, manifest.words) : []),
    [manifest]
  );

  // Load manifest
  useEffect(() => {
    if (!actId) return;
    let cancelled = false;
    fetch(`/v1/performances/${actId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`manifest ${r.status}`);
        return r.json();
      })
      .then((m) => { if (!cancelled) setManifest(m); })
      .catch((e: unknown) => {
        if (!cancelled) setManifestError(e instanceof Error ? e.message : String(e));
      });
    return () => { cancelled = true; };
  }, [actId]);

  // Live episode events
  useEffect(() => {
    if (!episodeId) return;
    const consumer = new EventConsumer();
    consumerRef.current = consumer;
    consumer.connect(episodeId, { role: 'stage' }).catch(() => {});
    return () => { consumer.disconnect(); consumerRef.current = null; };
  }, [episodeId]);

  // React to live show events: dialogue → say, keep → wave, enter → look
  const lastEventSeq = useRef(0);
  useEffect(() => {
    const avatar = avatarRef.current;
    if (!avatar || !events.length) return;
    for (const ev of events) {
      if (ev.seq <= lastEventSeq.current) continue;
      lastEventSeq.current = ev.seq;
      if (ev.type === 'stage.speak' && typeof ev.payload?.text === 'string') {
        avatar.say(ev.payload.text).catch(() => {});
      } else if (ev.type === 'verdict.keep') {
        avatar.wave().catch(() => {});
      } else if (ev.type === 'character.enter') {
        avatar.lookAtUser().catch(() => {});
      }
    }
  }, [events]);

  // Beat cue scheduler (driven by audio clock)
  const fireCuesUpTo = useCallback((ms: number) => {
    const avatar = avatarRef.current;
    for (const w of beatWindows) {
      if (w.start_ms <= ms && !firedBeatsRef.current.has(w.beat_id)) {
        firedBeatsRef.current.add(w.beat_id);
        if (!avatar) continue;
        if (w.beat.gesture) avatar.playClip(w.beat.gesture).catch(() => {});
        if (w.beat.type === 'punchline') avatar.lookAtUser().catch(() => {});
      }
    }
  }, [beatWindows]);

  const onTimeUpdate = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const ms = audio.currentTime * 1000;
    setTimeMs(ms);
    fireCuesUpTo(ms);
    if (manifest) {
      const hit = manifest.words.find((w) => ms >= w.start_ms && ms <= w.end_ms);
      setCaption(hit ? hit.word : '');
    }
  }, [manifest, fireCuesUpTo]);

  const play = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !audioUrl) return;
    firedBeatsRef.current.clear();
    audio.play().then(() => setPlaying(true)).catch(() => {});
  }, [audioUrl]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
    setPlaying(false);
  }, []);

  const formatTime = (ms: number): string => {
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  };

  return (
    <div style={{
      width: '100vw', height: '100vh', background: '#0a0a0f', color: '#e0e0e0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Stage */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <ThreeWsAvatar
          ref={avatarRef}
          avatarUrl={avatarUrl}
          performerName={performerName}
          fallbackHref={episodeId ? `/stage/${episodeId}` : '/'}
        />

        {/* Captions */}
        {caption && (
          <div style={{
            position: 'absolute', bottom: 64, left: '50%', transform: 'translateX(-50%)',
            fontSize: 28, fontWeight: 'bold', background: 'rgba(0,0,0,0.7)',
            padding: '6px 18px', borderRadius: 6,
          }}>
            {caption}
          </div>
        )}

        {/* HUD */}
        <div style={{
          position: 'absolute', top: 16, left: 16, fontSize: 12,
          fontFamily: 'monospace', opacity: 0.6,
        }}>
          {phase.replace(/_/g, ' ').toUpperCase()}
        </div>
        <div style={{
          position: 'absolute', top: 16, right: 16, fontSize: 18,
          fontFamily: 'monospace', fontWeight: 'bold',
        }}>
          {formatTime(timeMs)}
        </div>

        {/* Manifest status */}
        {!actId && (
          <div style={{
            position: 'absolute', bottom: 16, left: 16, fontSize: 12, opacity: 0.6,
            background: 'rgba(0,0,0,0.6)', padding: '6px 10px', borderRadius: 4,
          }}>
            live-avatar mode (no act — dialogue only). Add ?act=&lt;act_id&gt; for full sets.
          </div>
        )}
        {manifestError && (
          <div style={{
            position: 'absolute', bottom: 16, left: 16, fontSize: 12, color: '#ff6666',
            background: 'rgba(0,0,0,0.6)', padding: '6px 10px', borderRadius: 4,
          }}>
            manifest: {manifestError} — live-avatar mode.
          </div>
        )}
      </div>

      {/* Transport bar */}
      <div style={{
        padding: '12px 20px', borderTop: '1px solid #222',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        {audioUrl ? (
          playing
            ? <button onClick={pause} style={btnStyle}>⏸ PAUSE</button>
            : <button onClick={play} style={btnStyle}>▶ PLAY SET</button>
        ) : (
          <span style={{ fontSize: 12, opacity: 0.5 }}>
            {manifest ? 'no sealed audio on this performance' : 'connecting…'}
          </span>
        )}
        <span style={{ fontSize: 12, opacity: 0.5 }}>{performerName}</span>
      </div>

      <audio
        ref={audioRef}
        src={audioUrl || undefined}
        preload="auto"
        onTimeUpdate={onTimeUpdate}
        onEnded={() => setPlaying(false)}
      />
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  background: '#ff00aa', border: '1px solid #ff00aa', color: 'white',
  padding: '10px 20px', borderRadius: 6, cursor: 'pointer', fontSize: 13,
};
