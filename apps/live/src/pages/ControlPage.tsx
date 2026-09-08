/**
 * ControlPage — operator console for the show.
 *
 * Camera control, show commands, crowd monitoring.
 * This is what the human director sees.
 *
 * INVARIANT: control never mutates stage state directly. Every button
 * issues a canonical command (POST /live/:ep/command → EpisodeRoom →
 * persist → broadcast → stage executes). The crowd/phase/timer panels
 * are a READ view fed by an audience-role socket.
 *
 * URL: /control/:episodeId
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useShowStore, CameraPreset, ShowPhase } from '../store/showStore';
import { EventConsumer } from '../stage/EventConsumer';
import { ControlClient } from '../control/controlClient';

const PHASES: ShowPhase[] = [
  'pre_show', 'intro', 'lineup', 'character_enter', 'set_active',
  'post_set', 'judging', 'roast', 'transition', 'live_test',
  'model_reveal', 'elimination', 'finale', 'winner', 'outro', 'ended',
];

const CAMERA_PRESETS_LIST: CameraPreset[] = [
  'WIDE_STAGE', 'COMIC_MEDIUM', 'COMIC_CLOSE',
  'SIDE_STAGE', 'PANEL_WIDE', 'ELLA_CLOSE',
  'CHATGPT_CLOSE', 'STREAM_CLOSE',
];

const ADMIN_KEY_STORAGE = 'freaktown_admin_key';

export function ControlPage() {
  const { episodeId } = useParams<{ episodeId: string }>();
  const ep = episodeId ?? 'demo';

  const phase = useShowStore((s) => s.phase);
  const currentCamera = useShowStore((s) => s.currentCamera);
  const currentTimeMs = useShowStore((s) => s.currentTimeMs);
  const crowd = useShowStore((s) => s.crowd);
  const judgeScores = useShowStore((s) => s.judgeScores);
  const scoresRevealed = useShowStore((s) => s.scoresRevealed);

  const [adminKey, setAdminKey] = useState(
    () => localStorage.getItem(ADMIN_KEY_STORAGE) ?? ''
  );
  const [wsConnected, setWsConnected] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stageUrl, setStageUrl] = useState<string | null>(null);
  const [preload, setPreload] = useState({ performance_id: '', avatar_url: '', audio_url: '' });

  const client = useMemo(() => new ControlClient(ep, adminKey), [ep, adminKey]);
  const consumerRef = useRef<EventConsumer | null>(null);

  // READ view: audience-role socket (no privileged token needed).
  useEffect(() => {
    const consumer = new EventConsumer();
    consumerRef.current = consumer;
    consumer
      .connect(ep, { role: 'audience', sessionId: `control-${Date.now()}` })
      .then(() => setWsConnected(true))
      .catch(() => setWsConnected(false));
    const timer = window.setInterval(() => setWsConnected(consumer.connected), 2000);
    return () => {
      window.clearInterval(timer);
      consumer.disconnect();
      consumerRef.current = null;
      setWsConnected(false);
    };
  }, [ep]);

  useEffect(() => {
    localStorage.setItem(ADMIN_KEY_STORAGE, adminKey);
  }, [adminKey]);

  // Camera hotkeys 1-6 → canonical commands (not local mutations).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const idx = ['1', '2', '3', '4', '5', '6', '7', '8'].indexOf(e.key);
      if (idx >= 0) void runCommand(`camera ${CAMERA_PRESETS_LIST[idx]}`, () =>
        client.cutCamera(CAMERA_PRESETS_LIST[idx]));
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ep, adminKey]);

  async function runCommand(label: string, fn: () => Promise<unknown>): Promise<void> {
    if (busy) return;
    setBusy(label);
    setNotice(null);
    try {
      await fn();
      setNotice(`${label}: ok`);
    } catch (e) {
      setNotice(`${label}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(null);
    }
  }

  async function mintToken(): Promise<void> {
    await runCommand('mint stage token', async () => {
      const token = await client.mintStageToken('stage');
      const url = `${window.location.origin}/stage/${ep}?token=${encodeURIComponent(token)}`;
      setStageUrl(url);
    });
  }

  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const millis = Math.floor((ms % 1000) / 10);
    return `${minutes}:${seconds.toString().padStart(2, '0')}.${millis.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{
      width: '100vw', height: '100vh', background: '#0f0f14', color: '#e0e0e0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', borderBottom: '1px solid #333', background: '#1a1a24',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>FREAK TOWN</h1>
          <span style={{ fontSize: 12, opacity: 0.5 }}>CONTROL</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <input
            type="password"
            placeholder="admin key (ft_… or Privy JWT)"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            style={{
              background: '#0f0f14', border: '1px solid #444', color: '#e0e0e0',
              padding: '6px 10px', borderRadius: 4, fontSize: 12, width: 220,
            }}
          />
          <span style={{
            fontSize: 12, padding: '4px 8px', borderRadius: 4,
            background: wsConnected ? '#1a4a1a' : '#4a1a1a',
            color: wsConnected ? '#4aff4a' : '#ff4a4a',
          }}>
            {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
          <span style={{ fontSize: 12, opacity: 0.5 }}>EP: {ep}</span>
        </div>
      </header>

      {notice && (
        <div style={{
          padding: '8px 20px', fontSize: 12,
          background: notice.includes('failed') || notice.includes('4') ? '#3a1a1a' : '#1a3a2a',
          borderBottom: '1px solid #333',
        }}>
          {busy ? `${busy}…` : notice}
        </div>
      )}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{
          width: 240, borderRight: '1px solid #333', padding: 16,
          display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto',
        }}>
          <h3 style={{ fontSize: 12, opacity: 0.5, margin: 0 }}>CAMERAS (1-8)</h3>
          {CAMERA_PRESETS_LIST.map((preset, i) => (
            <button
              key={preset}
              disabled={busy !== null}
              onClick={() => void runCommand(`camera ${preset}`, () => client.cutCamera(preset))}
              style={{
                padding: '10px 12px',
                border: currentCamera === preset ? '2px solid #4a9' : '1px solid #444',
                borderRadius: 6,
                background: currentCamera === preset ? '#1a3a2a' : '#1a1a24',
                color: '#e0e0e0', cursor: 'pointer', textAlign: 'left', fontSize: 13,
              }}
            >
              <span style={{ fontFamily: 'monospace', marginRight: 8, opacity: 0.5 }}>{i + 1}</span>
              {preset.replace(/_/g, ' ')}
            </button>
          ))}

          <h3 style={{ fontSize: 12, opacity: 0.5, margin: '8px 0 0 0' }}>STAGE TOKEN</h3>
          <button
            disabled={busy !== null}
            onClick={() => void mintToken()}
            style={{
              padding: '10px 12px', border: '1px solid #49a', borderRadius: 6,
              background: 'transparent', color: '#49a', cursor: 'pointer', fontSize: 12,
            }}
          >
            MINT STAGE TOKEN
          </button>
          {stageUrl && (
            <div style={{ fontSize: 11, wordBreak: 'break-all', opacity: 0.8 }}>
              <div style={{ opacity: 0.5, marginBottom: 4 }}>STAGE URL (episode-scoped):</div>
              <a href={stageUrl} target="_blank" rel="noreferrer" style={{ color: '#49a' }}>
                {stageUrl.slice(0, 80)}…
              </a>
            </div>
          )}
        </div>

        <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
          <div style={{
            fontSize: 48, fontFamily: 'monospace', fontWeight: 'bold',
            textAlign: 'center', padding: 20, background: '#1a1a24', borderRadius: 8,
          }}>
            {formatTime(currentTimeMs)}
          </div>

          <div style={{ padding: 16, background: '#1a1a24', borderRadius: 8 }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>PHASE</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {PHASES.map((p) => (
                <button
                  key={p}
                  disabled={busy !== null}
                  onClick={() => void runCommand(`phase ${p}`, () => client.setPhase(p))}
                  style={{
                    padding: '6px 10px',
                    border: phase === p ? '2px solid #4a9' : '1px solid #444',
                    borderRadius: 4,
                    background: phase === p ? '#1a3a2a' : 'transparent',
                    color: '#e0e0e0', cursor: 'pointer', fontSize: 11,
                    textTransform: 'uppercase',
                  }}
                >
                  {p.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: 16, background: '#1a1a24', borderRadius: 8 }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>PRELOAD FREAK</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <ControlInput placeholder="performance_id" value={preload.performance_id}
                onChange={(v) => setPreload({ ...preload, performance_id: v })} />
              <ControlInput placeholder="avatar GLB URL" value={preload.avatar_url}
                onChange={(v) => setPreload({ ...preload, avatar_url: v })} />
              <ControlInput placeholder="set WAV URL" value={preload.audio_url}
                onChange={(v) => setPreload({ ...preload, audio_url: v })} />
              <ActionButton
                label={busy ? 'WORKING…' : 'PRELOAD → STAGE'}
                color="#49a"
                onClick={() => void runCommand('preload', () =>
                  client.preloadPerformance({
                    performance_id: preload.performance_id,
                    avatar_url: preload.avatar_url,
                    audio_url: preload.audio_url,
                  }))}
              />
            </div>
          </div>
        </div>

        <div style={{
          width: 280, borderLeft: '1px solid #333', padding: 16,
          display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto',
        }}>
          <div style={{ padding: 16, background: '#1a1a24', borderRadius: 8 }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>CROWD</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <MetricCard label="Viewers" value={crowd.active_viewers} />
              <MetricCard label="Laughers" value={crowd.unique_laughers} />
              <MetricCard label="Laughs" value={crowd.laugh_events} />
              <MetricCard label="Claps" value={crowd.claps} />
              <MetricCard label="Boos" value={crowd.boos} />
            </div>
          </div>

          <div style={{ padding: 16, background: '#1a1a24', borderRadius: 8 }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>
              JUDGES {scoresRevealed ? '(REVEALED)' : '(LOCKED)'}
            </h3>
            {judgeScores.length === 0 ? (
              <div style={{ fontSize: 12, opacity: 0.3 }}>No scores yet</div>
            ) : (
              judgeScores.map((s) => (
                <div key={s.name} style={{
                  padding: '8px 12px', border: '1px solid #333',
                  borderRadius: 4, marginBottom: 6,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</span>
                    <span style={{
                      fontSize: 16, fontWeight: 'bold',
                      color: s.score >= 7 ? '#4a9' : s.score >= 5 ? '#aa4' : '#a44',
                    }}>
                      {scoresRevealed ? s.score.toFixed(1) : '??'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>

          <div style={{ padding: 16, background: '#1a1a24', borderRadius: 8 }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>ACTIONS</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <ActionButton label="START SHOW" color="#4a9"
                onClick={() => void runCommand('start show', () => client.startShow())} />
              <ActionButton label="PAUSE" color="#aa4"
                onClick={() => void runCommand('pause', () => client.pauseShow())} />
              <ActionButton label="RESUME" color="#4a9"
                onClick={() => void runCommand('resume', () => client.resumeShow())} />
              <ActionButton label="START PERFORMANCE" color="#4a9"
                onClick={() => void runCommand('performance start', () =>
                  client.startPerformance(preload.performance_id || 'current'))} />
              <ActionButton label="END SET" color="#aa4"
                onClick={() => void runCommand('end set', () =>
                  client.endPerformance(preload.performance_id || 'current'))} />
              <ActionButton label="REVEAL SCORES" color="#49a"
                onClick={() => void runCommand('reveal', () => client.revealScores())} />
              <ActionButton label="END SHOW" color="#a44"
                onClick={() => void runCommand('end show', () => client.endShow())} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{ padding: '8px 10px', background: '#0f0f14', borderRadius: 4, textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 'bold' }}>{value}</div>
      <div style={{ fontSize: 10, opacity: 0.5, textTransform: 'uppercase' }}>{label}</div>
    </div>
  );
}

function ControlInput({ placeholder, value, onChange }: {
  placeholder: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <input
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: '#0f0f14', border: '1px solid #444', color: '#e0e0e0',
        padding: '8px 10px', borderRadius: 4, fontSize: 12, width: '100%',
      }}
    />
  );
}

function ActionButton({ label, color, onClick }: {
  label: string; color: string; onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '10px 12px', border: `1px solid ${color}`, borderRadius: 4,
        background: 'transparent', color, cursor: 'pointer', fontSize: 12,
        fontWeight: 500, textTransform: 'uppercase',
      }}
    >
      {label}
    </button>
  );
}
