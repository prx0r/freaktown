/**
 * StageRuntime — the single renderer for Freak Town.
 *
 * One Three.js scene. One AudioContext. One Transport.
 * Handles VRM loading, lip sync, motion cues, camera control.
 *
 * Used in both:
 * - /stage/:episodeId (production stage)
 * - /control/:episodeId (operator console)
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRM } from '@pixiv/three-vrm';
import { Transport } from './Transport';
import { AudioBus } from './AudioBus';
import { CameraDirector, CameraPresetName } from './CameraDirector';
import { LipSyncAdapter } from './LipSync';
import { EventConsumer } from './EventConsumer';
import { useShowStore, MotionCue, WordTiming, PerformancePlan } from '../store/showStore';

// ── Types ──────────────────────────────────────────────────────────

export type RuntimeStatus = 'EMPTY' | 'LOADING' | 'READY' | 'PLAYING' | 'PAUSED' | 'ENDED';

export interface PreloadSpec {
  avatarUrl: string;
  audioUrl: string;
  plan: PerformancePlan;
  wordTimings?: WordTiming[];
  walkoutUrl?: string;
}

export interface StageConfig {
  mode: 'live' | 'green-room';
  container: HTMLElement;
  background?: string;
}

// ── Stage Runtime ─────────────────────────────────────────────────

export class StageRuntime {
  // Three.js
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private clock: THREE.Clock;
  private mixer: THREE.AnimationMixer | null = null;
  private vrm: VRM | null = null;

  // Subsystems
  private transport: Transport;
  private audioBus: AudioBus;
  private cameraDirector: CameraDirector;
  private lipSync: LipSyncAdapter;
  private eventConsumer: EventConsumer;

  // Performance plan
  private plan: PerformancePlan | null = null;
  private wordTimings: WordTiming[] = [];
  private currentCueIndex: number = 0;

  // State
  private config: StageConfig;
  private animationFrameId: number | null = null;
  private unbindCameraKeyboard: (() => void) | null = null;

  /**
   * Explicit lifecycle. play() is a no-op until preload() resolves READY;
   * performance.start is only legal in READY (the show gates on the
   * stage.performance_ready ACK the executor sends after preload).
   */
  status: RuntimeStatus = 'EMPTY';

  // Gaze target (persistent Object3D — vrm.lookAt.target must be an Object3D)
  private gazeTarget: THREE.Object3D;

  constructor(config: StageConfig) {
    this.config = config;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(config.background || '#0a0a1a');

    // Camera
    this.camera = new THREE.PerspectiveCamera(
      45,
      config.container.clientWidth / config.container.clientHeight,
      0.1,
      100
    );

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setSize(config.container.clientWidth, config.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    config.container.appendChild(this.renderer.domElement);

    // Clock
    this.clock = new THREE.Clock();

    // Gaze target — VRM LookAt tracks this Object3D
    this.gazeTarget = new THREE.Object3D();
    this.gazeTarget.position.set(0, 1.5, 3);
    this.scene.add(this.gazeTarget);

    // Audio — one graph: transport → VOICE bus → analyser → MASTER.
    // The bus owns the lipsync tap; nothing else creates analysers.
    const audioContext = new AudioContext();
    this.transport = new Transport();
    this.transport.setAudioContext(audioContext);
    this.transport.setOnEnd(() => this.onTransportEnd());
    this.audioBus = new AudioBus(audioContext);
    this.transport.setOutputNode(this.audioBus.getGain('VOICE'));

    // Camera director
    this.cameraDirector = new CameraDirector(this.camera);
    this.cameraDirector.setClock(() => this.transport.currentTimeMs);

    // Lip sync reads the bus voice tap; mouth channel only.
    this.lipSync = new LipSyncAdapter();
    this.lipSync.attach(this.audioBus.getVoiceAnalyser());

    // Event consumer
    this.eventConsumer = new EventConsumer();

    // Setup lights
    this.setupLights();

    // Setup resize handler
    window.addEventListener('resize', this.handleResize);

    // CameraDirector owns keyboard mapping (StagePage must NOT add its own
    // handler — double handling crashes cutCamera with raw key strings).
    this.unbindCameraKeyboard = this.cameraDirector.bindKeyboard();
  }

  /** The shared consumer, so pages can attach one executor to it. */
  get consumer(): EventConsumer {
    return this.eventConsumer;
  }

  get audio(): AudioBus {
    return this.audioBus;
  }

  get director(): CameraDirector {
    return this.cameraDirector;
  }

  /** Current transport time in milliseconds. */
  get currentTimeMs(): number {
    return this.transport.currentTimeMs;
  }

  // ── Setup ────────────────────────────────────────────────────────

  private setupLights(): void {
    // Ambient
    const ambient = new THREE.AmbientLight(0xffffff, 0.5);
    this.scene.add(ambient);

    // Key light (warm)
    const keyLight = new THREE.DirectionalLight(0xfff5e6, 1.4);
    keyLight.position.set(2, 3, 2);
    keyLight.castShadow = true;
    this.scene.add(keyLight);

    // Fill light (cool)
    const fillLight = new THREE.DirectionalLight(0xe6f0ff, 0.4);
    fillLight.position.set(-2, 1, -1);
    this.scene.add(fillLight);

    // Rim light
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.3);
    rimLight.position.set(0, 2, -3);
    this.scene.add(rimLight);
  }

  private handleResize = (): void => {
    const w = this.config.container.clientWidth;
    const h = this.config.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  };

  // ── Asset Loading ────────────────────────────────────────────────

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

          // Set default pose
          vrm.humanoid?.resetNormalizedPose();

          // Connect lip sync
          this.lipSync.setVRM(vrm);

          resolve();
        },
        undefined,
        reject
      );
    });
  }

  async loadAudio(url: string): Promise<void> {
    await this.transport.loadAudio(url);
  }

  async loadAudioFromBytes(bytes: ArrayBuffer): Promise<void> {
    await this.transport.loadAudioFromBytes(bytes);
  }

  /**
   * Unlock audio from a user gesture (required on iPhone/mobile Safari
   * where Web Audio starts suspended). StagePage calls this on first tap.
   */
  async unlockAudio(): Promise<void> {
    const ctx = this.transport.getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      await ctx.resume();
    }
  }

  /** True while the AudioContext needs a user gesture to start. */
  isAudioLocked(): boolean {
    const ctx = this.transport.getAudioContext();
    return !!ctx && ctx.state === 'suspended';
  }

  // ── Performance Plan ─────────────────────────────────────────────

  setPlan(plan: PerformancePlan, wordTimings: WordTiming[] = []): void {
    this.plan = plan;
    this.wordTimings = wordTimings;
    this.currentCueIndex = 0;
  }

  /**
   * Load a Freak onto the stage: avatar GLB + set audio + plan + words.
   * EMPTY → LOADING → READY. play() is a no-op until READY.
   */
  async preload(spec: PreloadSpec): Promise<void> {
    this.setStatus('LOADING');
    await this.loadAvatar(spec.avatarUrl);
    await this.loadAudio(spec.audioUrl);
    this.setPlan(spec.plan, spec.wordTimings ?? []);
    this.setStatus('READY');
  }

  private statusListeners = new Set<(s: RuntimeStatus) => void>();

  onStatus(cb: (s: RuntimeStatus) => void): () => void {
    this.statusListeners.add(cb);
    return () => { this.statusListeners.delete(cb); };
  }

  private setStatus(s: RuntimeStatus): void {
    this.status = s;
    for (const cb of this.statusListeners) {
      try { cb(s); } catch { /* listener errors never break playback */ }
    }
  }

  // ── Transport Controls (state-machine gated) ──────────────────────

  play(): void {
    if (this.status !== 'READY' && this.status !== 'PAUSED' && this.status !== 'ENDED') return;
    this.lipSync.setActive(true);
    this.transport.play();
    this.setStatus('PLAYING');
    this.startAnimationLoop();
  }

  pause(): void {
    if (this.status !== 'PLAYING') return;
    this.lipSync.setActive(false);
    this.transport.pause();
    this.setStatus('PAUSED');
  }

  resume(): void {
    if (this.status !== 'PAUSED') return;
    this.play();
  }

  seek(ms: number): void {
    if (this.status !== 'PLAYING' && this.status !== 'PAUSED') return;
    this.transport.seek(ms);
    this.currentCueIndex = this.plan?.cues.findIndex(c => c.at_ms >= ms) ?? 0;
    if (this.currentCueIndex < 0) this.currentCueIndex = 0;
  }

  /** Called when the set audio naturally ends. */
  private onTransportEnd(): void {
    this.lipSync.setActive(false);
    this.setStatus('ENDED');
  }

  // ── Camera Control ──────────────────────────────────────────────

  cutCamera(preset: CameraPresetName): void {
    this.cameraDirector.cut(preset);
  }

  /** Gaze out at the crowd (character entrance default). */
  async lookAtAudience(): Promise<void> {
    this.gazeTarget.position.set(0, 1.5, 3);
  }

  // ── Audio Control ───────────────────────────────────────────────

  duckMusic(): void {
    this.audioBus.duckMusic();
  }

  unduckMusic(): void {
    this.audioBus.unduckMusic();
  }

  // ── Connection ──────────────────────────────────────────────────

  async connect(episodeId: string, token?: string): Promise<void> {
    await this.eventConsumer.connect(episodeId, { role: 'stage', token });
  }

  // ── Animation Loop ──────────────────────────────────────────────

  private startAnimationLoop(): void {
    if (this.animationFrameId !== null) return;

    const animate = () => {
      if (this.transport.state !== 'playing') {
        this.animationFrameId = null;
        return;
      }

      const delta = this.clock.getDelta();
      const currentTimeMs = this.transport.currentTimeMs;

      // Update VRM
      if (this.vrm) {
        this.vrm.update(delta);
      }

      // Update animation mixer
      if (this.mixer) {
        this.mixer.update(delta);
      }

      // Process motion cues
      this.processCues(currentTimeMs);

      // Update lip sync
      this.lipSync.update();

      // Update word highlighting
      this.updateWordHighlight(currentTimeMs);

      // Update store
      useShowStore.getState().setCurrentTime(currentTimeMs);

      // Render
      this.renderer.render(this.scene, this.camera);

      this.animationFrameId = requestAnimationFrame(animate);
    };

    this.animationFrameId = requestAnimationFrame(animate);
  }

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

    // Gesture
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

  private executeGaze(action: string, _intensity: number): void {
    if (!this.vrm?.lookAt) return;

    const targets: Record<string, THREE.Vector3> = {
      'gaze.audience': new THREE.Vector3(0, 1.5, 3),
      'gaze.ella': new THREE.Vector3(2, 1.5, 1),
      'gaze.ground': new THREE.Vector3(0, 0, 2),
      'gaze.sky': new THREE.Vector3(0, 3, 2),
      'gaze.left': new THREE.Vector3(-3, 1.5, 2),
      'gaze.right': new THREE.Vector3(3, 1.5, 2),
      'gaze.away': new THREE.Vector3(-2, 1.5, -1),
      'gaze.stare': new THREE.Vector3(0, 1.5, 3),
    };

    const target = targets[action];
    if (target) {
      this.gazeTarget.position.copy(target);
    }
  }

  private executeGesture(action: string, cue: MotionCue): void {
    if (action === 'locomotion.freeze') {
      if (this.mixer) {
        this.mixer.stopAllAction();
      }
      return;
    }

    // Placeholder: gesture would load and play a clip
    // In production: fetch motion asset from R2, create AnimationClip, play
  }

  // Emotion expressions driven by semantic beats. Targeted writes ONLY —
  // never resetValues() here: that would also clear the mouth visemes
  // (lipsync channel) and blink (timer channel) mid-frame and make them
  // fight. Channels: mouth = analyser, face = beats, blink = timer.
  private static readonly EMOTION_EXPRESSIONS = ['happy', 'angry', 'sad', 'surprised', 'neutral'];

  private executeFace(action: string, intensity: number): void {
    if (!this.vrm?.expressionManager) return;

    const em = this.vrm.expressionManager;

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
    if (!expr) return;

    for (const name of StageRuntime.EMOTION_EXPRESSIONS) {
      if (name !== expr) em.setValue(name, 0);
    }
    em.setValue(expr, intensity);
  }

  private executePose(action: string, cue: MotionCue): void {
    if (!this.vrm?.humanoid) return;

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

  // ── Cleanup ──────────────────────────────────────────────────────

  dispose(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }

    window.removeEventListener('resize', this.handleResize);
    this.unbindCameraKeyboard?.();
    this.unbindCameraKeyboard = null;

    this.transport.dispose();
    this.audioBus.dispose();
    this.cameraDirector.dispose();
    this.eventConsumer.disconnect();

    this.renderer.dispose();
  }
}
