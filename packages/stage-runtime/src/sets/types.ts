/**
 * SetDefinition — a set is data + a procedural builder (+ optional GLB decor).
 *
 *   seats      where characters go (position/yaw/role/pose)
 *   cameras    named presets; a preset may bind its target to a seat
 *   lighting   key/fill/rim colours + intensities (the builder applies them)
 *   props      named prop ids the builder knows (mics, cards…)
 *   overlays   DOM overlay hooks the stage page shows for this set
 *   environment.glb   optional CC0 decor loaded at runtime; procedural is always there
 *
 * Coordinates: metres, +Y up; avatars face +Z at yaw 0 (yaw rotates about Y).
 * Pure data (no three.js) so the registry and camera maths are unit-testable.
 */

export type Vec3 = [number, number, number];

export type SeatPose = 'standing' | 'seated';

export interface SeatAnchor {
  id: string;
  position: Vec3;
  /** Yaw in radians: 0 faces +Z (towards the default audience/camera). */
  rotation: number;
  role: string;
  pose: SeatPose;
  /** Seat a human may take from /play (poker). */
  open?: boolean;
}

export interface CameraPresetDef {
  /** Absolute camera position, or an offset in the seat's local frame when `seat` is set. */
  position: Vec3;
  /** Absolute target, or offset from the seat head when `seat` is set. */
  target: Vec3;
  fov: number;
  seat?: string;
  label?: string;
  /** Slow orbit around `target` (rad/s). */
  orbit?: number;
  /**
   * Portrait framing (aspect < 1, phones): replaces position/target and uses `fov`
   * as the vertical FOV as-is (no automatic widening). Additive (newsroom).
   */
  portrait?: { position: Vec3; target: Vec3; fov: number };
}

export interface LightingRig {
  ambient: { color: string; intensity: number };
  key: { color: string; intensity: number; position: Vec3 };
  fill?: { color: string; intensity: number; position: Vec3 };
  rim?: { color: string; intensity: number; position: Vec3 };
  background: string;
}

export interface EnvironmentDef {
  /** Procedural builder id (sets/builders) — always available, zero downloads. */
  builder: string;
  glb?: {
    url: string;
    license: string;
    source: string;
    /** Placement of the GLB scene (scale, yaw, offset) so its desk lines up with the seats. */
    transform?: { position?: Vec3; rotation?: number; scale?: number };
    /** Hide nodes whose names match (crop parts of a big scene). */
    hideNodes?: string[];
    /** Verified framing? Unverified GLBs load only with ?setglb=1. */
    verified?: boolean;
  };
}

export type OverlayHook = 'lower_third' | 'ticker' | 'headline' | 'on_air' | 'speaker_strap' | 'poker_hud';

export interface SetDefinition {
  id: string;
  name: string;
  description: string;
  environment: EnvironmentDef;
  seats: SeatAnchor[];
  /**
   * Extra standing positions characters can walk to (stage.move / sketch move-to).
   * Not cast seats: nothing sits there until something moves there. Camera cues
   * ("close:<mark>") and gaze targets resolve marks like seats.
   */
  marks?: SeatAnchor[];
  cameras: Record<string, CameraPresetDef>;
  /** Cue used on load and when nobody is talking. */
  defaultCamera: string;
  lighting: LightingRig;
  props: string[];
  overlays: OverlayHook[];
  /** Ordered camera buttons for /control. */
  controlCameras: string[];
  /** Max seats a cast may fill (defaults to seats.length). */
  maxCast?: number;
}
