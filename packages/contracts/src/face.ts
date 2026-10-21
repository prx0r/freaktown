/**
 * Face events (live stage). Ported vocabulary: see docs/LIVE-STAGE-EXTENDING.md §10.
 *   face.expression  {seat?, emotion|action, intensity?, duration_ms?}  semantic face cue
 *   face.blendshapes {seat?, weights: ARKit-52 name → 0..1}              live puppeteering stream
 *   face.affect      {seat?, a, v, p?, hold_ms?}                          affect servo (A/V/P ∈ [-1,1])
 * `seat` targets a set seat (multi-seat sets); omitted = the comedy-club performer.
 */
export const FACE_EVENT_TYPES = ["face.expression", "face.blendshapes", "face.affect"] as const;
export type FaceEventTypeV1 = (typeof FACE_EVENT_TYPES)[number];

export interface FaceExpressionPayloadV1 {
  seat?: string;
  /** Harness emotion ("smug", "deadpan") or a face action ("face.smile", "face_excited"). */
  emotion?: string;
  action?: string;
  intensity?: number;
  duration_ms?: number;
}
export interface FaceBlendshapesPayloadV1 { seat?: string; weights: Record<string, number> }
export interface FaceAffectPayloadV1 { seat?: string; a: number; v: number; p?: number; hold_ms?: number }

/** Mutuals character-harness acting beat (mutuals-beats/v1). */
export interface ActingBeatV1 { span: string; emotion?: string; register?: string; gesture?: string; camera?: string }
