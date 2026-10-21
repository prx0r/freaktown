/**
 * CameraDirector — camera presets and cuts for the stage.
 *
 * 6 initial presets. Each stores position, target, fov.
 * Cuts are instant — no tweens initially.
 * Real comedy camera cuts are cuts.
 *
 * Every cut generates a camera.cut event for ML data collection.
 */

import * as THREE from 'three';

import { CAMERA_NAMES, type CameraPresetV1 } from '@freaktown/contracts';

// ── Camera Presets ────────────────────────────────────────────────

export type CameraPresetName = CameraPresetV1;

export interface CameraPreset {
  position: [number, number, number];
  target: [number, number, number];
  fov: number;
  transitionMs?: number;
}

export const CAMERA_PRESETS: Record<CameraPresetName, CameraPreset> = {
  WIDE_STAGE: {
    position: [0, 2.4, 7.8],
    target: [0, 1.3, 0],
    fov: 46,
  },
  // Framed for a performer normalized to 1.7 m at the origin (StageRuntime).
  COMIC_MEDIUM: {
    position: [0, 1.48, 2.35],
    target: [0, 1.33, 0],
    fov: 30,
  },
  COMIC_CLOSE: {
    position: [0.08, 1.58, 1.6],
    target: [0, 1.52, 0],
    fov: 28,
  },
  // Club angle from house-left, so the mic stand (stage-right) never
  // crosses the face.
  SIDE_STAGE: {
    position: [-2.9, 1.7, 3.6],
    target: [0, 1.25, 0],
    fov: 36,
  },
  PANEL_WIDE: {
    position: [3, 1.6, 6],
    target: [0, 1.4, 0],
    fov: 50,
  },
  ELLA_CLOSE: {
    position: [2, 1.6, 2.5],
    target: [2, 1.5, 0],
    fov: 30,
  },
  // Judge closeups. Framing placeholders: no desk geometry exists yet,
  // so these frame the seat x-positions the desk layout specifies
  // (stream-left x=-2, chatgpt-right x=+4 relative to Ella at x=+2).
  CHATGPT_CLOSE: {
    position: [4, 1.6, 2.5],
    target: [4, 1.5, 0],
    fov: 30,
  },
  STREAM_CLOSE: {
    position: [-2, 1.6, 2.5],
    target: [-2, 1.5, 0],
    fov: 30,
  },
};

// Compile-time + runtime proof the preset table matches the contract:
// adding a preset anywhere without updating contracts breaks the build.
const _exhaustive: Record<CameraPresetV1, CameraPreset> = CAMERA_PRESETS;
export const CAMERA_PRESET_NAMES: ReadonlyArray<CameraPresetName> = CAMERA_NAMES;

// ── Keyboard Mapping ──────────────────────────────────────────────

const KEYBOARD_MAP: Record<string, CameraPresetName> = {
  '1': 'WIDE_STAGE',
  '2': 'COMIC_MEDIUM',
  '3': 'COMIC_CLOSE',
  '4': 'SIDE_STAGE',
  '5': 'PANEL_WIDE',
  '6': 'ELLA_CLOSE',
  '7': 'CHATGPT_CLOSE',
  '8': 'STREAM_CLOSE',
};

// ── Camera Director ───────────────────────────────────────────────

export type CameraCutCallback = (preset: CameraPresetName, set_time_ms: number) => void;

export class CameraDirector {
  private camera: THREE.PerspectiveCamera;
  private currentPreset: CameraPresetName = 'WIDE_STAGE';
  private onCut?: CameraCutCallback;
  private getCurrentTimeMs?: () => number;

  // Position smoothing (optional, for future smooth transitions)
  private targetPosition: THREE.Vector3 = new THREE.Vector3();
  private targetLookAt: THREE.Vector3 = new THREE.Vector3();

  constructor(camera: THREE.PerspectiveCamera) {
    this.camera = camera;

    // Apply default preset
    this.applyPreset('WIDE_STAGE');
  }

  // ── Configuration ────────────────────────────────────────────────

  setOnCut(callback: CameraCutCallback): void {
    this.onCut = callback;
  }

  setClock(clock: () => number): void {
    this.getCurrentTimeMs = clock;
  }

  // ── Cut Control ──────────────────────────────────────────────────

  /**
   * Cut to a camera preset. Instant, no tween.
   */
  cut(preset: CameraPresetName): void {
    if (preset === this.currentPreset) return;

    this.currentPreset = preset;
    this.applyPreset(preset);

    // Emit cut event
    const set_time_ms = this.getCurrentTimeMs?.() ?? 0;
    this.onCut?.(preset, set_time_ms);
  }

  /**
   * Get the current preset name.
   */
  getCurrentPreset(): CameraPresetName {
    return this.currentPreset;
  }

  /**
   * Get the current preset data.
   */
  getPresetData(preset: CameraPresetName): CameraPreset {
    return CAMERA_PRESETS[preset];
  }

  // ── Keyboard Control ─────────────────────────────────────────────

  /**
   * Handle keyboard input for camera cuts.
   * Returns true if the key was handled.
   */
  handleKeyboard(key: string): boolean {
    const preset = KEYBOARD_MAP[key];
    if (preset) {
      this.cut(preset);
      return true;
    }
    return false;
  }

  /**
   * Bind keyboard events for camera control.
   * Returns unbind function.
   */
  bindKeyboard(): () => void {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing in input fields
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      this.handleKeyboard(e.key);
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }

  // ── Preset Application ──────────────────────────────────────────

  private aspect = 16 / 9;

  /** Portrait screens get a slightly wider lens so the performer still fits. */
  setAspect(aspect: number): void {
    this.aspect = aspect > 0 ? aspect : 16 / 9;
    this.applyPreset(this.currentPreset);
  }

  private effectiveFov(fov: number): number {
    return this.aspect < 1 ? fov * (1 + (1 - this.aspect) * 0.6) : fov;
  }

  private applyPreset(preset: CameraPresetName): void {
    const data = CAMERA_PRESETS[preset];

    this.targetPosition.set(...data.position);
    this.camera.position.copy(this.targetPosition);
    this.camera.fov = this.effectiveFov(data.fov);
    this.camera.updateProjectionMatrix();

    // Set look-at target
    this.targetLookAt.set(...data.target);
    this.camera.lookAt(this.targetLookAt);
  }

  /**
   * Operator-style life on a locked-off shot: a few millimetres of slow
   * drift (cuts stay cuts). Call once per frame with wall time.
   */
  update(wallMs: number, amount = 1): void {
    const s = wallMs / 1000;
    const k = (this.currentPreset === 'COMIC_CLOSE' ? 0.6 : 1) * amount;
    this.camera.position.set(
      this.targetPosition.x + Math.sin(s * 0.31) * 0.025 * k,
      this.targetPosition.y + Math.sin(s * 0.47 + 1) * 0.012 * k,
      this.targetPosition.z + Math.sin(s * 0.23 + 2) * 0.03 * k,
    );
    this.camera.lookAt(this.targetLookAt);
  }

  // ── Cleanup ──────────────────────────────────────────────────────

  dispose(): void {
    // Nothing to dispose
  }
}
