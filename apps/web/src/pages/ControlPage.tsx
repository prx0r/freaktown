/**
 * ControlPage — operator console for the show.
 *
 * Camera control, show commands, crowd monitoring.
 * This is what the human director sees.
 *
 * URL: /control/:episodeId
 */

import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useShowStore, CameraPreset, CAMERA_PRESETS, ShowPhase } from '../store/showStore';

const PHASES: ShowPhase[] = [
  'pre_show', 'intro', 'lineup', 'character_enter', 'set_active',
  'post_set', 'judging', 'roast', 'transition', 'live_test',
  'model_reveal', 'elimination', 'finale', 'winner', 'outro', 'ended',
];

const CAMERA_PRESETS_LIST: CameraPreset[] = [
  'WIDE_STAGE', 'COMIC_MEDIUM', 'COMIC_CLOSE',
  'SIDE_STAGE', 'PANEL_WIDE', 'ELLA_CLOSE',
];

export function ControlPage() {
  const { episodeId } = useParams<{ episodeId: string }>();

  const phase = useShowStore((s) => s.phase);
  const currentCamera = useShowStore((s) => s.currentCamera);
  const currentTimeMs = useShowStore((s) => s.currentTimeMs);
  const crowd = useShowStore((s) => s.crowd);
  const judgeScores = useShowStore((s) => s.judgeScores);
  const scoresRevealed = useShowStore((s) => s.scoresRevealed);
  const isPlaying = useShowStore((s) => s.isPlaying);
  const appearances = useShowStore((s) => s.appearances);

  const setPhase = useShowStore((s) => s.setPhase);
  const setCamera = useShowStore((s) => s.setCamera);

  const [wsConnected, setWsConnected] = useState(false);

  // Format time as MM:SS.mmm
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const millis = Math.floor((ms % 1000) / 10);
    return `${minutes}:${seconds.toString().padStart(2, '0')}.${millis.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      background: '#0f0f14',
      color: '#e0e0e0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 20px',
        borderBottom: '1px solid #333',
        background: '#1a1a24',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>FREAK TOWN</h1>
          <span style={{ fontSize: 12, opacity: 0.5 }}>CONTROL</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{
            fontSize: 12,
            padding: '4px 8px',
            borderRadius: 4,
            background: wsConnected ? '#1a4a1a' : '#4a1a1a',
            color: wsConnected ? '#4aff4a' : '#ff4a4a',
          }}>
            {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
          <span style={{ fontSize: 12, opacity: 0.5 }}>EP: {episodeId}</span>
        </div>
      </header>

      {/* Main content */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left: Camera Control */}
        <div style={{
          width: 240,
          borderRight: '1px solid #333',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          <h3 style={{ fontSize: 12, opacity: 0.5, margin: 0 }}>CAMERAS (1-6)</h3>
          {CAMERA_PRESETS_LIST.map((preset, i) => (
            <button
              key={preset}
              onClick={() => setCamera(preset)}
              style={{
                padding: '10px 12px',
                border: currentCamera === preset ? '2px solid #4a9' : '1px solid #444',
                borderRadius: 6,
                background: currentCamera === preset ? '#1a3a2a' : '#1a1a24',
                color: '#e0e0e0',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: 13,
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontFamily: 'monospace', marginRight: 8, opacity: 0.5 }}>{i + 1}</span>
              {preset.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        {/* Center: Show State */}
        <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Timer */}
          <div style={{
            fontSize: 48,
            fontFamily: 'monospace',
            fontWeight: 'bold',
            textAlign: 'center',
            padding: 20,
            background: '#1a1a24',
            borderRadius: 8,
          }}>
            {formatTime(currentTimeMs)}
          </div>

          {/* Phase Control */}
          <div style={{
            padding: 16,
            background: '#1a1a24',
            borderRadius: 8,
          }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>PHASE</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {PHASES.map((p) => (
                <button
                  key={p}
                  onClick={() => setPhase(p)}
                  style={{
                    padding: '6px 10px',
                    border: phase === p ? '2px solid #4a9' : '1px solid #444',
                    borderRadius: 4,
                    background: phase === p ? '#1a3a2a' : 'transparent',
                    color: '#e0e0e0',
                    cursor: 'pointer',
                    fontSize: 11,
                    textTransform: 'uppercase',
                  }}
                >
                  {p.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Appearances */}
          <div style={{
            padding: 16,
            background: '#1a1a24',
            borderRadius: 8,
            flex: 1,
            overflow: 'auto',
          }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>APPEARANCES</h3>
            {appearances.length === 0 ? (
              <div style={{ fontSize: 12, opacity: 0.3 }}>No appearances yet</div>
            ) : (
              appearances.map((a, i) => (
                <div
                  key={a.id}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #333',
                    borderRadius: 4,
                    marginBottom: 6,
                    background: i === 0 ? '#1a2a1a' : 'transparent',
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{a.character_name}</div>
                  <div style={{ fontSize: 11, opacity: 0.5 }}>
                    #{a.draw_position} · {a.status}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: Crowd + Judges */}
        <div style={{
          width: 280,
          borderLeft: '1px solid #333',
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
          overflow: 'auto',
        }}>
          {/* Crowd */}
          <div style={{
            padding: 16,
            background: '#1a1a24',
            borderRadius: 8,
          }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>CROWD</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <MetricCard label="Viewers" value={crowd.active_viewers} />
              <MetricCard label="Laughers" value={crowd.unique_laughers} />
              <MetricCard label="Laughs" value={crowd.laugh_events} />
              <MetricCard label="Claps" value={crowd.claps} />
              <MetricCard label="Boos" value={crowd.boos} />
            </div>
          </div>

          {/* Judges */}
          <div style={{
            padding: 16,
            background: '#1a1a24',
            borderRadius: 8,
          }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>
              JUDGES {scoresRevealed ? '(REVEALED)' : '(LOCKED)'}
            </h3>
            {judgeScores.length === 0 ? (
              <div style={{ fontSize: 12, opacity: 0.3 }}>No scores yet</div>
            ) : (
              judgeScores.map((s) => (
                <div
                  key={s.name}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #333',
                    borderRadius: 4,
                    marginBottom: 6,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</span>
                    <span style={{
                      fontSize: 16,
                      fontWeight: 'bold',
                      color: s.score >= 7 ? '#4a9' : s.score >= 5 ? '#aa4' : '#a44',
                    }}>
                      {scoresRevealed ? s.score.toFixed(1) : '??'}
                    </span>
                  </div>
                  {scoresRevealed && s.feedback && (
                    <div style={{ fontSize: 11, opacity: 0.6, marginTop: 4 }}>
                      {s.feedback.slice(0, 100)}...
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Quick Actions */}
          <div style={{
            padding: 16,
            background: '#1a1a24',
            borderRadius: 8,
          }}>
            <h3 style={{ fontSize: 12, opacity: 0.5, margin: '0 0 12px 0' }}>ACTIONS</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <ActionButton label="START SHOW" color="#4a9" />
              <ActionButton label="END SET" color="#aa4" />
              <ActionButton label="REVEAL SCORES" color="#49a" />
              <ActionButton label="NEXT CONTESTANT" color="#a94" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Helper Components ─────────────────────────────────────────────

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      padding: '8px 10px',
      background: '#0f0f14',
      borderRadius: 4,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 18, fontWeight: 'bold' }}>{value}</div>
      <div style={{ fontSize: 10, opacity: 0.5, textTransform: 'uppercase' }}>{label}</div>
    </div>
  );
}

function ActionButton({ label, color }: { label: string; color: string }) {
  return (
    <button
      style={{
        padding: '10px 12px',
        border: `1px solid ${color}`,
        borderRadius: 4,
        background: 'transparent',
        color,
        cursor: 'pointer',
        fontSize: 12,
        fontWeight: 500,
        textTransform: 'uppercase',
        transition: 'all 0.15s',
      }}
    >
      {label}
    </button>
  );
}
