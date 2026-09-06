/**
 * Green Room — the creator's studio.
 *
 * Character shelf, script editor, WATCH button, stage directions.
 * Same renderer as live show. If it works here, it works live.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';

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
  stage_directions: {
    id: string;
    at_word: number;
    action: string;
    description: string;
  }[];
  version: number;
}

interface PerformancePlan {
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

export default function GreenRoom() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedChar, setSelectedChar] = useState<Character | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [plan, setPlan] = useState<PerformancePlan | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [highlightedWord, setHighlightedWord] = useState(-1);
  const [directionInput, setDirectionInput] = useState('');
  const [directionTarget, setDirectionTarget] = useState<number>(-1);
  const [view, setView] = useState<'shelf' | 'editor' | 'watch'>('shelf');

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

  // Compile
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

  // ── Character Shelf ────────────────────────────────────────────

  if (view === 'shelf') {
    return (
      <div className="green-room">
        <h1>The Green Room</h1>
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
                <span>Word {directionTarget}: "{words[directionTarget]}"</span>
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
            ▶ WATCH
          </button>
        </div>
      </div>
    );
  }

  // ── Watch Mode ─────────────────────────────────────────────────

  if (view === 'watch' && plan && draft) {
    return (
      <div className="green-room watch">
        <div className="watch-header">
          <button onClick={() => setView('editor')}>← Edit</button>
          <h2>{selectedChar?.name} — Rehearsal</h2>
        </div>

        <div className="stage-container" id="stage-mount">
          {/* StageRenderer mounts here */}
          <div className="stage-placeholder">
            <p>Stage renders here with three-vrm avatar</p>
            <p>{plan.cue_count} motion cues, {plan.duration_ms / 1000}s</p>
          </div>
        </div>

        <div className="script-overlay">
          {draft.script}
        </div>

        <div className="watch-actions">
          <button onClick={() => setIsPlaying(!isPlaying)}>
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
          <button onClick={enterShow} className="btn-primary">
            🎬 ENTER TONIGHT'S SHOW
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
