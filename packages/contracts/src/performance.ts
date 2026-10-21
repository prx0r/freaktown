// Performance-plan + show-event shapes shared by StageRuntime, apps/live
// and the set adapter. Moved here from apps/live/src/store/showStore.ts so
// the runtime never imports app code (stage-runtime README debt #3).
// Additive only: new optional fields, never renamed/removed ones.

import type { CameraPresetV1 } from "./show";

export interface WordTiming {
  word: string;
  start_ms: number;
  end_ms: number;
  index: number;
  /** Beat this word belongs to (set adapter fills it). */
  beat_id?: string;
}

export interface MotionCue {
  at_ms: number;
  action: string;
  motion_asset_id: string | null;
  duration_ms: number;
  intensity: number;
  bone_mask: string;
  layer: "base" | "upper" | "head" | "face";
  metadata?: Record<string, any>;
}

/** Envelope mouth span measured from the composed wav (puppet_qa.envelope_cues). */
export interface MouthSpan {
  start_ms: number;
  end_ms: number;
  shape?: string;
}

/** Plan-scheduled camera cut (auto director). Deterministic: part of the
 * preloaded plan, so replaying the event log reproduces every cut. */
export interface CameraCue {
  at_ms: number;
  camera: CameraPresetV1;
  reason?: string;
}

export interface PlanBeat {
  id: string;
  type: string;
  start_ms: number;
  end_ms: number;
  text: string;
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
  // ── additive (live stage) ──
  title?: string;
  character_id?: string;
  beats?: PlanBeat[];
  word_timings?: WordTiming[];
  mouth?: MouthSpan[];
  camera_cues?: CameraCue[];
  source?: Record<string, unknown>;
}

export interface ShowEvent {
  seq: number;
  type: string;
  actor: string;
  payload: Record<string, any>;
  created_at: string;
  effective_at?: string;
}

export type ShowPhase =
  | "pre_show" | "intro" | "lineup" | "character_enter" | "set_active"
  | "post_set" | "judging" | "roast" | "transition" | "live_test"
  | "model_reveal" | "elimination" | "finale" | "winner" | "outro" | "ended";
