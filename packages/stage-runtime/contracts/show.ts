// Canonical TypeScript wire contracts for the freaktown stage.
// GENERATED MIRROR — source of truth is split, deliberately:
//   - show-event shapes mirror /home/ubuntu/freaktown/backend/contracts.py
//     (ShowEventV1, ReactionRawV1, SnapshotV1, CrowdUpdateV1,
//      CameraCutPayloadV1, PerformancePreloadPayloadV1, EllaSenseV1,
//      EllaActionV1, JudgeReactPayloadV1, PanelSeatPayloadV1,
//      JudgeModeV1, CharacterModesV1)
//   - the pog -> show mapping lives in pogtown's
//     services/api/stage-adapter.mjs and is parity-tested against this file
//     (pogtown tests/contracts-parity.test.mjs).
// snake_case on the wire, everywhere.

export type CameraPresetV1 =
  | "WIDE_STAGE" | "COMIC_MEDIUM" | "COMIC_CLOSE"
  | "SIDE_STAGE" | "PANEL_WIDE" | "ELLA_CLOSE"
  | "CHATGPT_CLOSE" | "STREAM_CLOSE";

export const CAMERA_NAMES: CameraPresetV1[] = [
  "WIDE_STAGE", "COMIC_MEDIUM", "COMIC_CLOSE",
  "SIDE_STAGE", "PANEL_WIDE", "ELLA_CLOSE",
  "CHATGPT_CLOSE", "STREAM_CLOSE",
];

export type JudgeReaction =
  | "iris_narrow" | "nod" | "flare" | "stillness"
  | "pulse" | "thinking" | "glow" | "freeze"
  | "jitter" | "burst" | "morph";

export type PanelSeat = "stream-left" | "ella-center" | "chatgpt-right";

export type ReactionKind =
  | "laugh" | "clap" | "boo" | "crickets" | "groan" | "love" | "wtf";

export interface ShowEventV1 {
  seq: number;
  type: string;
  actor?: string;
  payload?: Record<string, unknown>;
  created_at?: string;
  effective_at?: string | null;
}

export interface ReactionRawV1 {
  seq: number;
  event_id: string;
  episode_id: string;
  performance_id: string;
  session_id: string;
  client_seq: number;
  type: "reaction";
  reaction: ReactionKind;
  set_time_ms?: number;
  server_received_at: string;
  source: string;
}

export interface SnapshotV1 {
  episode_id: string;
  phase: string;
  active_appearance_id?: string | null;
  seq: number;
  is_paused?: boolean;
}

export interface CrowdUpdateV1 {
  laugh_events: number;
  claps: number;
  boos: number;
  crickets: number;
  groans: number;
  unique_laughers: number;
}

export interface CameraCutPayloadV1 {
  camera: CameraPresetV1;
  performance_id?: string | null;
  set_time_ms?: number | null;
  source: string;
}

export interface PerformancePreloadPayloadV1 {
  performance_id: string;
  avatar_url: string;
  audio_url: string;
  walkout_url?: string | null;
  plan?: Record<string, unknown>;
  word_timings?: unknown[];
  episode_id?: string | null;
}

export interface EllaSenseV1 {
  episode_id: string;
  phase: string;
  active_appearance_id?: string | null;
  seq: number;
  is_paused?: boolean;
  set_time_ms?: number | null;
  crowd: CrowdUpdateV1;
  pot_cents: number;
  updated_at: string;
}

export type EllaActionSource = "reflex-v1" | "live-v1" | "judge-v1";

export interface EllaActionV1 {
  set_time_ms?: number | null;
  trigger: string;
  action: string;
  latency_ms: number;
  source: EllaActionSource;
  text?: string | null;
}

export interface JudgeReactPayloadV1 {
  judge: string;
  reaction: JudgeReaction;
  performance_id?: string | null;
  set_time_ms?: number | null;
}

export interface PanelSeatPayloadV1 {
  seat: PanelSeat;
  character_id?: string | null;
  character_name?: string | null;
  reason?: string | null;
}

export interface JudgeModeV1 {
  seat?: PanelSeat | null;
  camera_profile?: string | null;
  animations?: string[] | null;
  ui_theme?: Record<string, unknown> | null;
  authority?: "full" | "commentary" | "none" | null;
  critique_persona?: string | null;
}

export interface CharacterModesV1 {
  performer?: Record<string, unknown> | null;
  judge?: JudgeModeV1 | null;
}

// Runtime validator for camera-cut payloads (no zod dependency by design:
// this file must stay dependency-free so every consumer shares it).
// EpisodeRoom drops unknown cameras here — never persisted, never broadcast.
export function validateCameraCut(input: unknown):
  | { ok: true; value: CameraCutPayloadV1 }
  | { ok: false; error: string } {
  if (typeof input !== "object" || input === null) {
    return { ok: false, error: "not an object" };
  }
  const o = input as Record<string, unknown>;
  if (typeof o.camera !== "string" || !CAMERA_NAMES.includes(o.camera as CameraPresetV1)) {
    return { ok: false, error: "unknown camera" };
  }
  const performance_id = o.performance_id ?? null;
  if (performance_id !== null && typeof performance_id !== "string") {
    return { ok: false, error: "bad performance_id" };
  }
  const set_time_ms = o.set_time_ms ?? null;
  if (set_time_ms !== null && typeof set_time_ms !== "number") {
    return { ok: false, error: "bad set_time_ms" };
  }
  const source = o.source ?? null;
  if (source !== null && typeof source !== "string") {
    return { ok: false, error: "bad source" };
  }
  return {
    ok: true,
    value: {
      camera: o.camera as CameraPresetV1,
      performance_id: performance_id as string | null | undefined,
      set_time_ms: set_time_ms as number | null | undefined,
      source: (source as string) ?? "unknown",
    },
  };
}
