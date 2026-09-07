/**
 * Green Room — the creator's studio.
 *
 * Character shelf, script editor, rehearsal stage, submit.
 * Same StageRuntime as the live show. If it works here, it works live.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { StageRuntime, RuntimeStatus } from '../stage/StageRuntime';
import type { PerformancePlan as StagePlan, MotionCue, WordTiming as StageWordTiming } from '../store/showStore';

// ── Types ──────────────────────────────────────────────────────────

interface Character {
  id: string;
  name: string;
  premise: string;
  body_class: string;
  voice_id: string;
  engine_preset: string;
  signature_moves: { id: string; name: string }[];
}

interface WordTiming {
  word: string;
  start_ms: number;
  end_ms: number;
  index: number;
}

interface Draft {
  id: string;
  script: string;
  word_count: number;
  estimated_duration_ms: number;
  audio_duration_ms: number;
  duration_status: 'green' | 'amber' | 'red';
  voice_id: string;
  word_timings: WordTiming[];
  audio_r2_key?: string;
  stage_directions: {
    id: string;
    at_word: number;
    action: string;
    description: string;
  }[];
  version: number;
}

interface BackendPlan {
  appearance_id: string;
  body_class: string;
  duration_ms: number;
  energy: number;
  stillness: number;
  gesture_density: number;
  cue_count: number;
  cues: {
    at_ms: number;
    action: string;
    layer: string;
    intensity: number;
  }[];
}

const API = ''; // same origin

// ── Green Room App ─────────────────────────────────────────────────

export function GreenRoom() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedChar, setSelectedChar] = useState<Character | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [plan, setPlan] = useState<BackendPlan | null>(null);
  const [view, setView] = useState<'shelf' | 'editor' | 'watch'>('shelf');
  const [directionInput, setDirectionInput] = useState('');
  const [directionTarget, setDirectionTarget] = useState<number>(-1);

  // Rehearsal state
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus>('EMPTY');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [highlightedWord, setHighlightedWord] = useState(-1);
  const [audioLocked, setAudioLocked] = useState(false);

  const stageContainerRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<StageRuntime | null>(null);

  // Load characters
  useEffect(() => {
    fetch(`${API}/v1/green-room/characters`)
      .then(r => r.json())
      .then(d => setCharacters(d.characters || []));
  }, []);

  // Lucky Dip
  const luckyDip = async () => {
    const r = await fetch(`${API}/v1/green-room/lucky-dip`, { method: 'POST' });
    const d = await r.json();
    setCharacters(prev => [...prev, d.character]);
    selectCharacter(d.character);
  };

  // Select character → create draft
  const selectCharacter = async (char: Character) => {
    setSelectedChar(char);
    const r = await fetch(`${API}/v1/green-room/drafts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ character_id: char.id }),
    });
    const d = await r.json();
    setDraft(d.draft);
    setView('editor');
  };

  // Update script
  const updateScript = async (script: string) => {
    if (!draft) return;
    const r = await fetch(`${API}/v1/green-room/drafts/${draft.id}/script`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script }),
    });
    const d = await r.json();
    setDraft(d.draft);
  };

  // Synthesize voice
  const synthesize = async () => {
    if (!draft) return;
    const r = await fetch(`${API}/v1/green-room/drafts/${draft.id}/synthesize`, {
      method: 'POST',
    });
    const d = await r.json();
    setDraft(d.draft);
  };

  // Add stage direction
  const addDirection = async () => {
    if (!draft || directionTarget < 0 || !directionInput.trim()) return;
    const r = await fetch(`${API}/v1/green-room/drafts/${draft.id}/directions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ at_word: directionTarget, description: directionInput }),
    });
    const d = await r.json();
    setDraft(prev => prev ? {
      ...prev,
      stage_directions: [...prev.stage_directions, d.direction],
    } : prev);
    setDirectionInput('');
    setDirectionTarget(-1);
  };

  // Compile → enter watch mode
  const compile = async () => {
    if (!draft) return;
    const r = await fetch(`${API}/v1/green-room/compile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_id: draft.id }),
    });
    const d = await r.json();
    setPlan(d.plan);
    setView('watch');
  };

  // Enter show
  const enterShow = async () => {
    if (!draft) return;
    await fetch(`${API}/v1/green-room/enter-show`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft_id: draft.id, episode_id: 'current' }),
    });
    alert('Performance sealed and entered into tonight\'s show!');
  };

  // ── StageRuntime lifecycle (watch mode) ────────────────────────────

  useEffect(() => {
    if (view !== 'watch' || !stageContainerRef.current || !plan || !draft) return;

    const container = stageContainerRef.current;
    const runtime = new StageRuntime({
      mode: 'green-room',
      container,
      background: '#0a0a1a',
    });
    runtimeRef.current = runtime;

    const offStatus = runtime.onStatus((s) => setRuntimeStatus(s));

    // Word highlighting callback
    runtime.setWordCallback((index) => {
      setHighlightedWord(index);
    });

    // Load audio if we have a synthesized draft
    if (draft.audio_duration_ms > 0) {
      // Audio is served from the backend green room synthesis endpoint
      // For now, we use a placeholder URL — in production this would be R2 signed URL
      const audioUrl = `${API}/v1/green-room/drafts/${draft.id}/audio`;

      // Build the StagePlan from the backend plan
      const stagePlan: StagePlan = {
        appearance_id: plan.appearance_id || draft.id,
        body_class: plan.body_class || 'humanoid-v1',
        duration_ms: plan.duration_ms,
        base_idle_asset_id: null,
        energy: plan.energy || 0.5,
        stillness: plan.stillness || 0.5,
        gesture_density: plan.gesture_density || 0.5,
        cue_count: plan.cue_count,
        cues: plan.cues.map(c => ({
          at_ms: c.at_ms,
          action: c.action,
          motion_asset_id: null,
          duration_ms: 1000,
          intensity: c.intensity || 0.5,
          bone_mask: 'all',
          layer: (c.layer as 'base' | 'upper' | 'head' | 'face') || 'base',
        })),
      };

      // Convert word timings to StageWordTiming format
      const wordTimings: StageWordTiming[] = (draft.word_timings || []).map(wt => ({
        word: wt.word,
        start_ms: wt.start_ms,
        end_ms: wt.end_ms,
        index: wt.index,
      }));

      // Preload: audio + plan + word timings
      // Note: no avatar GLB yet — stage renders without avatar until we have one
      runtime.preload({
        avatarUrl: '', // no avatar GLB yet
        audioUrl,
        plan: stagePlan,
        wordTimings,
      }).catch((e) => {
        console.warn('[green-room] preload failed (avatar may be missing):', e);
        // Still set plan so transport/cues work even without avatar
        runtime.setPlan(stagePlan, wordTimings);
      });
    }

    // Time update for UI
    const timeInterval = setInterval(() => {
      if (runtime.status === 'PLAYING') {
        setCurrentTimeMs(runtime.currentTimeMs);
      }
    }, 100);

    return () => {
      clearInterval(timeInterval);
      offStatus();
      runtime.dispose();
      runtimeRef.current = null;
      setHighlightedWord(-1);
      setCurrentTimeMs(0);
    };
  }, [view, plan?.appearance_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Play/Pause controls
  const handlePlayPause = useCallback(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;

    if (isPlaying) {
      runtime.pause();
      setIsPlaying(false);
    } else {
      // Unlock audio on first user gesture (iPhone)
      if (runtime.isAudioLocked()) {
        runtime.unlockAudio().catch(() => {});
      }
      runtime.play();
      setIsPlaying(true);
    }
  }, [isPlaying]);

  // ── Character Shelf ────────────────────────────────────────────

  if (view === 'shelf') {
    return (
      <div className="green-room">
        <h1>Freak Town Studio</h1>
        <p className="subtitle">Create a Freak. Write their minute. Watch them perform.</p>
        <div className="character-shelf">
          {characters.map(char => (
            <div key={char.id} className="character-card" onClick={() => selectCharacter(char)}>
              <div className="character-avatar">{char.body_class === 'quadruped-v1' ? '🐕' : char.body_class === 'rigid-object-v1' ? ' toaster' : '🎭'}</div>
              <h3>{char.name}</h3>
              <p>{char.premise}</p>
              <span className="engine-tag">{char.engine_preset}</span>
            </div>
          ))}
          <div className="character-card new" onClick={luckyDip}>
            <div className="character-avatar">🎲</div>
            <h3>Lucky Dip</h3>
            <p>Random character</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Script Editor ──────────────────────────────────────────────

  if (view === 'editor' && draft) {
    const words = draft.script.split(/\s+/);
    return (
      <div className="green-room editor">
        <div className="editor-header">
          <button onClick={() => setView('shelf')}>← Back</button>
          <h2>{selectedChar?.name || 'Character'}</h2>
          <span className={`duration-badge ${draft.duration_status}`}>
            ~{(draft.estimated_duration_ms / 1000).toFixed(1)}s
          </span>
        </div>

        <div className="editor-body">
          <div className="script-panel">
            <textarea
              value={draft.script}
              onChange={(e) => updateScript(e.target.value)}
              placeholder="Write your minute here..."
              rows={12}
            />
            <div className="script-stats">
              <span>{draft.word_count} words</span>
              <span>~{(draft.estimated_duration_ms / 1000).toFixed(0)}s estimated</span>
              {draft.audio_duration_ms > 0 && (
                <span>{(draft.audio_duration_ms / 1000).toFixed(1)}s actual</span>
              )}
            </div>
          </div>

          <div className="words-panel">
            <h3>Click a word to add a direction:</h3>
            <div className="word-grid">
              {words.map((word, i) => {
                const hasDirection = draft.stage_directions.some(d => d.at_word === i);
                return (
                  <span
                    key={i}
                    className={`word ${hasDirection ? 'has-direction' : ''} ${i === highlightedWord ? 'highlighted' : ''}`}
                    onClick={() => setDirectionTarget(i)}
                  >
                    {word}
                  </span>
                );
              })}
            </div>

            {directionTarget >= 0 && (
              <div className="direction-bar">
                <span>Word {directionTarget}: &quot;{words[directionTarget]}&quot;</span>
                <input
                  value={directionInput}
                  onChange={(e) => setDirectionInput(e.target.value)}
                  placeholder="What should happen? (e.g. stare at Ella, shrug)"
                  onKeyDown={(e) => e.key === 'Enter' && addDirection()}
                />
                <button onClick={addDirection}>Add</button>
              </div>
            )}
          </div>
        </div>

        <div className="editor-actions">
          <button onClick={synthesize} className="btn-secondary">
            🔊 Synthesize Voice
          </button>
          <button onClick={compile} className="btn-primary" disabled={!draft.audio_duration_ms}>
            ▶ REHEARSE
          </button>
        </div>
      </div>
    );
  }

  // ── Watch / Rehearse Mode ──────────────────────────────────────

  if (view === 'watch' && plan && draft) {
    const formatTime = (ms: number) => {
      const s = Math.floor(ms / 1000);
      return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    };

    return (
      <div className="green-room watch">
        <div className="watch-header">
          <button onClick={() => setView('editor')}>← Edit</button>
          <h2>{selectedChar?.name} — Rehearsal</h2>
          <span className="runtime-badge">{runtimeStatus}</span>
        </div>

        <div className="stage-container" ref={stageContainerRef} id="stage-mount">
          {/* StageRuntime mounts here — Three.js canvas + VRM avatar */}
        </div>

        {/* Audio unlock overlay for iPhone */}
        {audioLocked && (
          <button
            className="audio-unlock"
            onClick={() => {
              runtimeRef.current?.unlockAudio().catch(() => {});
              setAudioLocked(false);
            }}
          >
            TAP TO ENABLE AUDIO
          </button>
        )}

        <div className="watch-overlay">
          <div className="time-display">{formatTime(currentTimeMs)}</div>

          {/* Highlighted word during playback */}
          {highlightedWord >= 0 && draft.word_timings[highlightedWord] && (
            <div className="word-highlight">
              {draft.word_timings[highlightedWord].word}
            </div>
          )}
        </div>

        <div className="watch-controls">
          <button onClick={handlePlayPause} className="btn-play">
            {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
          </button>
          <button onClick={enterShow} className="btn-primary">
            🎬 ENTER TONIGHT&apos;S SHOW
          </button>
        </div>

        <div className="cue-timeline">
          {plan.cues.map((cue, i) => (
            <div
              key={i}
              className="cue-marker"
              style={{ left: `${(cue.at_ms / plan.duration_ms) * 100}%` }}
              title={`${cue.action} (${cue.layer})`}
            />
          ))}
        </div>
      </div>
    );
  }

  return null;
}

export default GreenRoom;
