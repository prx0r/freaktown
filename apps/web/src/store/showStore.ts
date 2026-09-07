/**
 * Show Store — Zustand state for the live show.
 *
 * Single source of truth for:
 * - Episode state (phase, active appearance, timing)
 * - Camera state (current preset, transitions)
 * - Audio state (transport, volume levels)
 * - Crowd state (reactions, aggregates)
 * - Judge state (locked scores, reveal)
 */

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────

export type ShowPhase =
  | 'pre_show'
  | 'intro'
  | 'lineup'
  | 'character_enter'
  | 'set_active'
  | 'post_set'
  | 'judging'
  | 'roast'
  | 'transition'
  | 'live_test'
  | 'model_reveal'
  | 'elimination'
  | 'finale'
  | 'winner'
  | 'outro'
  | 'ended';

export type CameraPreset =
  | 'WIDE_STAGE'
  | 'COMIC_MEDIUM'
  | 'COMIC_CLOSE'
  | 'SIDE_STAGE'
  | 'PANEL_WIDE'
  | 'ELLA_CLOSE';

export interface CameraCut {
  type: 'camera.cut';
  performance_id: string;
  camera: CameraPreset;
  set_time_ms: number;
  source: 'human_director' | 'auto_director';
}

export interface ShowEvent {
  seq: number;
  type: string;
  actor: string;
  payload: Record<string, any>;
  created_at: string;
  effective_at?: string;
}

export interface Appearance {
  id: string;
  draw_position: number;
  comedian_id: string;
  character_name: string;
  body_class: string;
  status: 'queued' | 'playing' | 'completed';
}

export interface JudgeScore {
  name: string;
  score: number;
  feedback: string;
  verdict?: 'KEEP' | 'CUT';
  award?: 'GOLDEN_TICKET' | 'none';
  confidence?: number;
}

export interface CrowdState {
  active_viewers: number;
  unique_laughers: number;
  laugh_events: number;
  claps: number;
  boos: number;
}

// ── Performance Plan Types (shared with StageRuntime) ─────────────

export interface WordTiming {
  word: string;
  start_ms: number;
  end_ms: number;
  index: number;
}

export interface MotionCue {
  at_ms: number;
  action: string;
  motion_asset_id: string | null;
  duration_ms: number;
  intensity: number;
  bone_mask: string;
  layer: 'base' | 'upper' | 'head' | 'face';
  metadata?: Record<string, any>;
}

export interface PerformancePlan {
  appearance_id: string;
  body_class: string;
  duration_ms: number;
  base_idle_asset_id: string | null;
  energy: number;
  stillness: number;
  gesture_density: number;
  cue_count: number;
  cues: MotionCue[];
}

// ── Store ──────────────────────────────────────────────────────────

export interface ShowState {
  // Episode
  episodeId: string | null;
  phase: ShowPhase;
  isPaused: boolean;
  startedAt: number | null;

  // Appearances
  appearances: Appearance[];
  activeAppearanceIndex: number;

  // Camera
  currentCamera: CameraPreset;
  cameraCuts: CameraCut[];

  // Audio
  isPlaying: boolean;
  currentTimeMs: number;

  // Crowd
  crowd: CrowdState;

  // Judges
  judgeScores: JudgeScore[];
  scoresRevealed: boolean;

  // Events
  events: ShowEvent[];
  lastSeq: number;

  // Actions
  setEpisode: (id: string) => void;
  setPhase: (phase: ShowPhase) => void;
  setPaused: (paused: boolean) => void;
  setPlaying: (playing: boolean) => void;
  setCurrentTime: (ms: number) => void;
  setCamera: (camera: CameraPreset, source?: 'human_director' | 'auto_director') => void;
  setAppearances: (appearances: Appearance[]) => void;
  setActiveAppearance: (index: number) => void;
  setCrowd: (crowd: Partial<CrowdState>) => void;
  setJudgeScores: (scores: JudgeScore[]) => void;
  setScoresRevealed: (revealed: boolean) => void;
  addEvent: (event: ShowEvent) => void;
  applyEvent: (event: ShowEvent) => void;
}

const CAMERA_PRESETS: Record<CameraPreset, { position: [number, number, number]; target: [number, number, number]; fov: number }> = {
  WIDE_STAGE:    { position: [0, 2.4, 7.8],  target: [0, 1.3, 0], fov: 46 },
  COMIC_MEDIUM:  { position: [0, 1.75, 4.2], target: [0, 1.45, 0], fov: 34 },
  COMIC_CLOSE:   { position: [0, 1.72, 2.6], target: [0, 1.62, 0], fov: 28 },
  SIDE_STAGE:    { position: [4, 1.8, 5],    target: [0, 1.3, 0], fov: 40 },
  PANEL_WIDE:    { position: [3, 1.6, 6],    target: [0, 1.4, 0], fov: 50 },
  ELLA_CLOSE:    { position: [2, 1.6, 2.5],  target: [2, 1.5, 0], fov: 30 },
};

export { CAMERA_PRESETS };

export const useShowStore = create<ShowState>((set, get) => ({
  // Episode
  episodeId: null,
  phase: 'pre_show',
  isPaused: false,
  startedAt: null,

  // Appearances
  appearances: [],
  activeAppearanceIndex: 0,

  // Camera
  currentCamera: 'WIDE_STAGE',
  cameraCuts: [],

  // Audio
  isPlaying: false,
  currentTimeMs: 0,

  // Crowd
  crowd: { active_viewers: 0, unique_laughers: 0, laugh_events: 0, claps: 0, boos: 0 },

  // Judges
  judgeScores: [],
  scoresRevealed: false,

  // Events
  events: [],
  lastSeq: 0,

  // Actions
  setEpisode: (id) => set({ episodeId: id }),
  setPhase: (phase) => set({ phase }),
  setPaused: (paused) => set({ isPaused: paused }),
  setPlaying: (playing) => set({ isPlaying: playing }),
  setCurrentTime: (ms) => set({ currentTimeMs: ms }),

  setCamera: (camera, source = 'human_director') => {
    const state = get();
    const cut: CameraCut = {
      type: 'camera.cut',
      performance_id: state.episodeId || '',
      camera,
      set_time_ms: state.currentTimeMs,
      source,
    };
    set({
      currentCamera: camera,
      cameraCuts: [...state.cameraCuts, cut],
    });
  },

  setAppearances: (appearances) => set({ appearances }),
  setActiveAppearance: (index) => set({ activeAppearanceIndex: index }),
  setCrowd: (crowd) => set((s) => ({ crowd: { ...s.crowd, ...crowd } })),
  setJudgeScores: (scores) => set({ judgeScores: scores }),
  setScoresRevealed: (revealed) => set({ scoresRevealed: revealed }),

  addEvent: (event) => set((s) => ({
    events: [...s.events, event],
    lastSeq: Math.max(s.lastSeq, event.seq),
  })),

  applyEvent: (event) => {
    const state = get();

    // Persist event
    state.addEvent(event);

    // Apply state changes based on event type
    switch (event.type) {
      case 'show.start':
        set({ phase: 'intro', startedAt: Date.now() });
        break;
      case 'show.pause':
        set({ isPaused: true });
        break;
      case 'show.resume':
        set({ isPaused: false });
        break;
      case 'show.end':
        set({ phase: 'ended', isPlaying: false });
        break;
      case 'phase.change':
        set({ phase: event.payload.phase as ShowPhase });
        break;
      case 'character.enter':
        set({ phase: 'set_active' });
        break;
      case 'character.exit':
        set({ phase: 'post_set' });
        break;
      case 'camera.cut':
        set({ currentCamera: event.payload.camera as CameraPreset });
        break;
      case 'performance.start':
        set({ isPlaying: true, currentTimeMs: 0 });
        break;
      case 'performance.end':
        set({ isPlaying: false });
        break;
      case 'crowd.aggregate':
        state.setCrowd(event.payload);
        break;
      case 'judge.ella.locked':
      case 'judge.chatgpt.locked':
      case 'judge.stream.locked':
        // Scores are locked but not revealed yet
        break;
      case 'judge.reveal':
        set({ scoresRevealed: true });
        break;
    }
  },
}));
