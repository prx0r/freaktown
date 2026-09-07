/**
 * Shared wire contracts — the single source of truth for show data shapes.
 *
 * Imported by BOTH the browser stage and the Worker live room, so the
 * two runtimes cannot drift (episode_id vs episodeId, created_at vs
 * createdAt, laughs vs laugh_events — all settled here, once).
 *
 * Rule: snake_case on the wire, everywhere. camelCase never leaves a
 * process boundary.
 *
 * Python mirror: backend/contracts.py (Pydantic). Golden fixtures in
 * tests validate both sides against the same JSON.
 */

import { z } from 'zod';

// ── freaktown.event.v1 ─────────────────────────────────────────────

export const ShowEventV1 = z.object({
  seq: z.number().int().nonnegative(),
  type: z.string().min(1),
  actor: z.string(),
  payload: z.record(z.unknown()).default({}),
  created_at: z.string().datetime({ offset: true }),
  effective_at: z.string().datetime({ offset: true }).optional(),
});

export type ShowEventV1 = z.infer<typeof ShowEventV1>;

// ── freaktown.reaction.v1 (raw ML event) ───────────────────────────

export const ReactionTypeV1 = z.enum([
  'laugh', 'clap', 'boo', 'crickets', 'groan', 'love', 'wtf',
]);

export type ReactionTypeV1 = z.infer<typeof ReactionTypeV1>;

export const ReactionRawV1 = z.object({
  seq: z.number().int().nonnegative(),
  event_id: z.string().uuid(),
  episode_id: z.string(),
  performance_id: z.string(),
  session_id: z.string(),
  client_seq: z.number().int().positive(),
  type: z.literal('reaction'),
  reaction: ReactionTypeV1,
  set_time_ms: z.number().nonnegative(),
  server_received_at: z.string().datetime({ offset: true }),
  source: z.string().min(1),
});

export type ReactionRawV1 = z.infer<typeof ReactionRawV1>;

// ── freaktown.snapshot.v1 ──────────────────────────────────────────

export const SnapshotV1 = z.object({
  episode_id: z.string(),
  phase: z.string(),
  active_appearance_id: z.string().nullable(),
  seq: z.number().int().nonnegative(),
  is_paused: z.boolean(),
});

export type SnapshotV1 = z.infer<typeof SnapshotV1>;

// ── freaktown.crowd.v1 ─────────────────────────────────────────────

export const CrowdUpdateV1 = z.object({
  laugh_events: z.number().int().nonnegative(),
  claps: z.number().int().nonnegative(),
  boos: z.number().int().nonnegative(),
  crickets: z.number().int().nonnegative(),
  groans: z.number().int().nonnegative(),
  unique_laughers: z.number().int().nonnegative(),
});

export type CrowdUpdateV1 = z.infer<typeof CrowdUpdateV1>;

// ── camera.cut payload ─────────────────────────────────────────────

export const CameraPresetV1 = z.enum([
  'WIDE_STAGE', 'COMIC_MEDIUM', 'COMIC_CLOSE',
  'SIDE_STAGE', 'PANEL_WIDE', 'ELLA_CLOSE',
]);

export type CameraPresetV1 = z.infer<typeof CameraPresetV1>;

export const CameraCutPayloadV1 = z.object({
  camera: CameraPresetV1,
  performance_id: z.string().nullable().optional(),
  set_time_ms: z.number().nullable().optional(),
  source: z.enum(['human_director', 'auto_director']),
});

export type CameraCutPayloadV1 = z.infer<typeof CameraCutPayloadV1>;

// ── performance.preload payload ────────────────────────────────────

export const PerformancePreloadPayloadV1 = z.object({
  performance_id: z.string().min(1),
  avatar_url: z.string().min(1),
  audio_url: z.string().min(1),
  walkout_url: z.string().optional(),
  plan: z.unknown(),
  word_timings: z.unknown().optional(),
  episode_id: z.string().optional(),
});

export type PerformancePreloadPayloadV1 = z.infer<typeof PerformancePreloadPayloadV1>;

// ── freaktown.delivery.v1 (stage-facing subset) ────────────────────

export const DeliveryBeatV1 = z.object({
  id: z.string(),
  type: z.string(),
  text: z.string(),
  delivery: z.object({
    pace: z.number().optional(),
    energy: z.number().optional(),
    emphasis: z.number().optional(),
    expression: z.string().optional(),
  }).catchall(z.unknown()).optional(),
  pause_before_ms: z.number().optional(),
  pause_after_ms: z.number().optional(),
  stage: z.string().optional(),
  gesture: z.string().optional(),
  camera: z.string().optional(),
  sound: z.string().optional(),
});

export type DeliveryBeatV1 = z.infer<typeof DeliveryBeatV1>;

export const DeliveryV1 = z.object({
  version: z.literal('freaktown.delivery.v1'),
  voice: z.object({
    provider: z.string(),
    voice_id: z.string(),
  }).catchall(z.unknown()),
  beats: z.array(DeliveryBeatV1).min(1),
});

export type DeliveryV1 = z.infer<typeof DeliveryV1>;

// ── freaktown.avatar.v1 ────────────────────────────────────────────

export const AvatarCapabilitiesV1 = z.object({
  humanoid: z.boolean().optional(),
  blink: z.boolean().optional(),
  visemes: z.array(z.string()).optional(),
  look_at: z.boolean().optional(),
  expressions: z.array(z.string()).optional(),
}).catchall(z.unknown());

export type AvatarCapabilitiesV1 = z.infer<typeof AvatarCapabilitiesV1>;

export const AvatarV1 = z.object({
  version: z.literal('freaktown.avatar.v1'),
  format: z.literal('vrm'),
  vrm_version: z.string().optional(),
  asset: z.string().min(1),
  capabilities: AvatarCapabilitiesV1.optional(),
});

export type AvatarV1 = z.infer<typeof AvatarV1>;

// ── freaktown.bundle.v1 (intake shape) ─────────────────────────────

export const BundleV1 = z.object({
  character: z.object({
    name: z.string().min(1),
    species: z.string().optional(),
    premise: z.string().optional(),
    vibe: z.string().optional(),
    voice: z.string().optional(),
    avatar_url: z.string().optional(),
  }).catchall(z.unknown()),
  delivery: DeliveryV1,
  avatar: AvatarV1.optional(),
  episode_id: z.string().optional(),
});

export type BundleV1 = z.infer<typeof BundleV1>;
