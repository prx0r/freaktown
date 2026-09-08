/**
 * Stage Renderer — reads PerformancePlan, drives three-vrm avatar.
 *
 * This is the single renderer used in both Green Room and Live Show.
 * Same PerformancePlan. Same avatar. Same audio. Same WebAudio clock.
 *
 * Green Room = brick wall + rehearsal mic
 * Live Show = main stage + audience + lights
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRM, VRMExpressionManager } from '@pixiv/three-vrm';

// ── Types ──────────────────────────────────────────────────────────

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

export interface StageConfig {
  mode: 'green-room' | 'live-show';
  background: string;        // color or gradient
  cameraPosition: [number, number, number];
  showEllaPlaceholder: boolean;
}

// ── Stage Renderer ─────────────────────────────────────────────────

export class StageRenderer {
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private mixer: THREE.AnimationMixer | null = null;
  private vrm: VRM | null = null;
  private clock: THREE.Clock;

  // Audio
  private audioContext: AudioContext | null = null;
  private audioBuffer: AudioBuffer | null = null;
  private audioSource: AudioBufferSourceNode | null = null;
  private audioStartTime: number = 0;

  // Performance plan
  private plan: PerformancePlan | null = null;
  private wordTimings: WordTiming[] = [];
  private isPlaying: boolean = false;
  private currentCueIndex: number = 0;
  private animationFrameId: number | null = null;

  // Lip sync
  private analyser: AnalyserNode | null = null;
  private lipSyncData: Uint8Array<ArrayBuffer> | null = null;

  // Gaze target (persistent Object3D — vrm.lookAt.target must be an Object3D)
  private gazeTarget: THREE.Object3D;

  constructor(container: HTMLElement, config: StageConfig) {
    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(config.background || '#1a1a2e');

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    this.camera.position.set(...config.cameraPosition);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    container.appendChild(this.renderer.domElement);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xfff5e6, 1.2);
    keyLight.position.set(2, 3, 2);
    this.scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xe6f0ff, 0.4);
    fillLight.position.set(-2, 1, -1);
    this.scene.add(fillLight);

    // Clock
    this.clock = new THREE.Clock();

    // Gaze target — VRM LookAt tracks this Object3D
    this.gazeTarget = new THREE.Object3D();
    this.gazeTarget.position.set(0, 1.5, 3);
    this.scene.add(this.gazeTarget);

    // Resize handler
    window.addEventListener('resize', () => {
      this.camera.aspect = container.clientWidth / container.clientHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(container.clientWidth, container.clientHeight);
    });
  }

  // ── Load Avatar ─────────────────────────────────────────────────

  async loadAvatar(url: string): Promise<void> {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    return new Promise((resolve, reject) => {
      loader.load(
        url,
        async (gltf) => {
          const vrm = gltf.userData.vrm as VRM;
          if (!vrm) {
            reject(new Error('No VRM found in GLB'));
            return;
          }

          this.vrm = vrm;
          this.scene.add(vrm.scene);
          this.mixer = new THREE.AnimationMixer(vrm.scene);

          // VRM LookAt tracks our persistent gaze target
          if (vrm.lookAt) {
            vrm.lookAt.target = this.gazeTarget;
          }

          // Set default T-pose to rest pose
          vrm.humanoid?.resetNormalizedPose();

          resolve();
        },
        undefined,
        reject
      );
    });
  }

  // ── Load Audio ──────────────────────────────────────────────────

  async loadAudio(url: string): Promise<void> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }

    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

    // Set up analyser for lip sync
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.lipSyncData = new Uint8Array(this.analyser.frequencyBinCount);
  }

  loadAudioFromBytes(bytes: ArrayBuffer): Promise<void> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }

    return this.audioContext.decodeAudioData(bytes).then((buffer) => {
      this.audioBuffer = buffer;
      this.analyser = this.audioContext!.createAnalyser();
      this.analyser.fftSize = 256;
      this.lipSyncData = new Uint8Array(this.analyser.frequencyBinCount);
    });
  }

  // ── Set Plan ────────────────────────────────────────────────────

  setPlan(plan: PerformancePlan, wordTimings: WordTiming[] = []): void {
    this.plan = plan;
    this.wordTimings = wordTimings;
    this.currentCueIndex = 0;
  }

  // ── Playback ────────────────────────────────────────────────────

  play(): void {
    if (!this.audioBuffer || !this.audioContext || !this.plan) return;

    // Resume audio context if suspended
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }

    // Start audio
    this.audioSource = this.audioContext.createBufferSource();
    this.audioSource.buffer = this.audioBuffer;

    // Connect: source → analyser → destination
    if (this.analyser) {
      this.audioSource.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
    } else {
      this.audioSource.connect(this.audioContext.destination);
    }

    this.audioStartTime = this.audioContext.currentTime;
    this.audioSource.start(0);
    this.isPlaying = true;
    this.currentCueIndex = 0;

    // Start render loop
    this.animate();

    // When audio ends
    this.audioSource.onended = () => {
      this.isPlaying = false;
    };
  }

  pause(): void {
    if (this.audioSource) {
      this.audioSource.stop();
    }
    this.isPlaying = false;
  }

  seekTo(ms: number): void {
    // Pause, restart audio at offset, replay cues from this point
    this.pause();
    if (this.audioBuffer && this.audioContext) {
      this.audioSource = this.audioContext.createBufferSource();
      this.audioSource.buffer = this.audioBuffer;
      this.audioSource.connect(this.audioContext.destination);
      this.audioStartTime = this.audioContext.currentTime - (ms / 1000);
      this.audioSource.start(0, ms / 1000);
      this.isPlaying = true;
      this.currentCueIndex = this.plan?.cues.findIndex(c => c.at_ms >= ms) || 0;
      this.animate();
    }
  }

  getCurrentTimeMs(): number {
    if (!this.audioContext || !this.isPlaying) return 0;
    return (this.audioContext.currentTime - this.audioStartTime) * 1000;
  }

  // ── Animation Loop ──────────────────────────────────────────────

  private animate = (): void => {
    if (!this.isPlaying) return;

    const delta = this.clock.getDelta();
    const currentTimeMs = this.getCurrentTimeMs();

    // Update VRM
    if (this.vrm) {
      this.vrm.update(delta);
    }

    // Update animation mixer
    if (this.mixer) {
      this.mixer.update(delta);
    }

    // Process cues
    this.processCues(currentTimeMs);

    // Lip sync from audio analyser
    this.updateLipSync();

    // Update word highlighting
    this.updateWordHighlight(currentTimeMs);

    // Render
    this.renderer.render(this.scene, this.camera);

    this.animationFrameId = requestAnimationFrame(this.animate);
  };

  // ── Cue Processing ──────────────────────────────────────────────

  private processCues(timeMs: number): void {
    if (!this.plan || !this.vrm) return;

    while (
      this.currentCueIndex < this.plan.cues.length &&
      this.plan.cues[this.currentCueIndex].at_ms <= timeMs
    ) {
      const cue = this.plan.cues[this.currentCueIndex];
      this.executeCue(cue);
      this.currentCueIndex++;
    }
  }

  private executeCue(cue: MotionCue): void {
    if (!this.vrm) return;

    const action = cue.action;

    // Gaze
    if (action.startsWith('gaze.')) {
      this.executeGaze(action, cue.intensity);
    }

    // Gesture (will be driven by animation clips when loaded)
    if (action.startsWith('gesture.') || action === 'locomotion.freeze') {
      this.executeGesture(action, cue);
    }

    // Face expression
    if (action.startsWith('face.') || action.startsWith('reaction.')) {
      this.executeFace(action, cue.intensity);
    }

    // Pose
    if (action.startsWith('pose.')) {
      this.executePose(action, cue);
    }
  }

  private executeGaze(action: string, intensity: number): void {
    if (!this.vrm?.lookAt) return;

    // Map gaze actions to lookAt target positions
    const targets: Record<string, THREE.Vector3> = {
      'gaze.audience': new THREE.Vector3(0, 1.5, 3),
      'gaze.ella': new THREE.Vector3(2, 1.5, 1),
      'gaze.ground': new THREE.Vector3(0, 0, 2),
      'gaze.sky': new THREE.Vector3(0, 3, 2),
      'gaze.left': new THREE.Vector3(-3, 1.5, 2),
      'gaze.right': new THREE.Vector3(3, 1.5, 2),
      'gaze.away': new THREE.Vector3(-2, 1.5, -1),
      'gaze.stare': new THREE.Vector3(0, 1.5, 3), // fixed stare
    };

    const target = targets[action];
    if (target) {
      this.gazeTarget.position.copy(target);
    }
  }

  private executeGesture(action: string, cue: MotionCue): void {
    // For MVP: simple procedural gestures
    // Full implementation loads motion clips from R2
    if (!this.vrm?.humanoid) return;

    if (action === 'locomotion.freeze') {
      // Stop all current animations
      if (this.mixer) {
        this.mixer.stopAllAction();
      }
      return;
    }

    // Placeholder: gesture would load and play a clip
    // In production: fetch motion asset from R2, create AnimationClip, play
  }

  private executeFace(action: string, intensity: number): void {
    if (!this.vrm?.expressionManager) return;

    const em = this.vrm.expressionManager;

    // Reset all expressions first
    em.resetValues();

    // Map action to VRM expression
    const exprMap: Record<string, string> = {
      'face.smile': 'happy',
      'face.frown': 'sad',
      'face.annoyed': 'angry',
      'face.surprised': 'surprised',
      'face.deadpan': 'neutral',
      'face.smug': 'happy',
      'face.disgusted': 'angry',
      'reaction.confused': 'surprised',
      'reaction.annoyed': 'angry',
      'reaction.shock': 'surprised',
      'reaction.dead_stare': 'neutral',
    };

    const expr = exprMap[action];
    if (expr) {
      em.setValue(expr, intensity);
    }
  }

  private executePose(action: string, cue: MotionCue): void {
    // Procedural pose adjustments
    if (!this.vrm?.humanoid) return;

    // For MVP: head tilt as proxy for pose
    const head = this.vrm.humanoid.getNormalizedBoneNode('head');
    if (!head) return;

    switch (action) {
      case 'pose.lean_forward':
        head.rotation.x = -0.1 * cue.intensity;
        break;
      case 'pose.lean_back':
        head.rotation.x = 0.1 * cue.intensity;
        break;
      case 'pose.confident':
        head.rotation.x = 0;
        head.rotation.z = 0;
        break;
      case 'pose.slump':
        head.rotation.x = 0.15;
        head.rotation.z = 0.05;
        break;
    }
  }

  // ── Lip Sync ────────────────────────────────────────────────────

  private updateLipSync(): void {
    if (!this.analyser || !this.lipSyncData || !this.vrm?.expressionManager) return;

    this.analyser.getByteFrequencyData(this.lipSyncData);

    // Simple energy-based viseme
    let sum = 0;
    for (let i = 0; i < 32; i++) {
      sum += this.lipSyncData[i];
    }
    const avg = sum / 32 / 255; // 0-1

    // Map to mouth open (VRM mouth expression)
    this.vrm.expressionManager.setValue('aa', avg * 0.8);
    this.vrm.expressionManager.setValue('oh', avg * 0.2);
  }

  // ── Word Highlight ──────────────────────────────────────────────

  private currentWordIndex: number = -1;
  private onWordChange?: (index: number, word: string) => void;

  setWordCallback(cb: (index: number, word: string) => void): void {
    this.onWordChange = cb;
  }

  private updateWordHighlight(timeMs: number): void {
    for (let i = 0; i < this.wordTimings.length; i++) {
      const wt = this.wordTimings[i];
      if (timeMs >= wt.start_ms && timeMs <= wt.end_ms) {
        if (i !== this.currentWordIndex) {
          this.currentWordIndex = i;
          this.onWordChange?.(i, wt.word);
        }
        break;
      }
    }
  }

  // ── Cleanup ─────────────────────────────────────────────────────

  dispose(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    if (this.audioSource) {
      try { this.audioSource.stop(); } catch {}
    }
    this.renderer.dispose();
  }
}
