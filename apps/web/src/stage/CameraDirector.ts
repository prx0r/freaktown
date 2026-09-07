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

// ── Camera Presets ────────────────────────────────────────────────

export type CameraPresetName =
  | 'WIDE_STAGE'
  | 'COMIC_MEDIUM'
  | 'COMIC_CLOSE'
  | 'SIDE_STAGE'
  | 'PANEL_WIDE'
  | 'ELLA_CLOSE';

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
  COMIC_MEDIUM: {
    position: [0, 1.75, 4.2],
    target: [0, 1.45, 0],
    fov: 34,
  },
  COMIC_CLOSE: {
    position: [0, 1.72, 2.6],
    target: [0, 1.62, 0],
    fov: 28,
  },
  SIDE_STAGE: {
    position: [4, 1.8, 5],
    target: [0, 1.3, 0],
    fov: 40,
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
};

// ── Keyboard Mapping ──────────────────────────────────────────────

const KEYBOARD_MAP: Record<string, CameraPresetName> = {
  '1': 'WIDE_STAGE',
  '2': 'COMIC_MEDIUM',
  '3': 'COMIC_CLOSE',
  '4': 'SIDE_STAGE',
  '5': 'PANEL_WIDE',
  '6': 'ELLA_CLOSE',
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

  private applyPreset(preset: CameraPresetName): void {
    const data = CAMERA_PRESETS[preset];

    this.camera.position.set(...data.position);
    this.camera.fov = data.fov;
    this.camera.updateProjectionMatrix();

    // Set look-at target
    this.targetLookAt.set(...data.target);
    this.camera.lookAt(this.targetLookAt);
  }

  // ── Cleanup ──────────────────────────────────────────────────────

  dispose(): void {
    // Nothing to dispose
  }
}
