/**
 * StageRuntime — the single renderer for FUNNIER.
 *
 * One Three.js scene. One AudioContext. One Transport (the show clock).
 * Data/events in, performance out. No React, no app imports: the host
 * injects a ClockSink (timer readout) and a RoomStore (state mirror).
 *
 *   performer  = AvatarDriver (VRM → GLB → BASIC) + Performer (body/face)
 *   mouth      = MouthTrack on the media clock (plan) | analyser (live audio)
 *   camera     = CameraDirector presets; plan camera_cues + camera.cut events
 *   room       = StageSet (brick wall, mic, lights, audience)
 *
 * Lifecycle: EMPTY → LOADING → READY → PLAYING ⇄ PAUSED → ENDED.
 * play() is a no-op until READY; the show gates performance.start on the
 * stage.performance_ready ACK the executor sends after preload.
 */

import * as THREE from 'three';
import type { CameraCue, MotionCue, PerformancePlan, WordTiming } from '@funnier/contracts';
import { Transport } from './Transport';
import { AudioBus } from './AudioBus';
import { CameraDirector, type CameraPresetName } from './CameraDirector';
import { EventConsumer } from './EventConsumer';
import { StageSet } from './StageSet';
import { COMEDY_CLUB } from './sets/definitions';
import { SfxSynth } from './SfxSynth';
import { NULL_CLOCK_SINK, type ClockSink, type RoomStore } from './ports';
import type { LiveTransport } from './live/LiveTransport';
import { loadAvatar } from './avatars/loadAvatar';
import type { AvatarCapabilities, AvatarDriver, Emotions, Visemes } from './avatars/types';
import { MouthTrack } from './performance/MouthTrack';
import { toPhonetics } from './performance/MouthTrack';
import type { PhoneticViseme } from './performance/MouthTrack';
import { ProsodyTrack } from './performance/ProsodyTrack';
import type { ProsodyFrame } from './performance/ProsodyTrack';
import { Performer } from './performance/Performer';
import { FaceChannel } from './face/FaceChannel';
import { emotionToFaceAction } from './face/vocab';

// ── Types ──────────────────────────────────────────────────────────

export type RuntimeStatus = 'EMPTY' | 'LOADING' | 'READY' | 'PLAYING' | 'PAUSED' | 'ENDED';

export interface PreloadSpec {
  avatarUrl: string;
  audioUrl: string;
  plan: PerformancePlan;
  wordTimings?: WordTiming[];
  walkoutUrl?: string;
  name?: string;
  seed?: string;
  /** Take visemes.json (TalkingHead-en phonetics). Preferred over vowel
   *  groups when present; may also ride the adapted plan. */
  visemes?: { visemes: string[]; vtimes: number[]; vdurations: number[] };
  /** Take aus.json (AU prosody track). Brows/eyes/blink under beats. */
  aus?: { frames: ProsodyFrame[] };
}

export interface StageConfig {
  container: HTMLElement;
  mode?: 'live' | 'green-room';
  background?: string;
  clockSink?: ClockSink;
  store?: RoomStore;
  transport?: LiveTransport;
  /** Bind number keys to local camera cuts (debug only; live cuts are events). */
  keyboard?: boolean;
  /** Frame-stepped capture mode: no realtime loop, no audio output. */
  capture?: boolean;
  shadows?: boolean;
  sign?: string;
  /** 'low' = half-res, no shadows/AA (software GL, old phones, CI). */
  quality?: 'high' | 'low';
  /** CPU skinning/morphs for GPUs without vertex texture fetch (CI/SwiftShader). */
  cpuSkinning?: boolean;
  /** Optional comedy-club environment variant id (COMEDY_CLUB.variants, e.g. 'dive'); procedural if unset. */
  setVariant?: string;
  /** Resolve asset URLs (variant GLBs). */
  resolveUrl?: (u: string) => string;
}

export interface CutRecord {
  camera: CameraPresetName;
  set_time_ms: number;
  source: 'auto_director' | 'human_director' | 'initial';
  wall_ms: number;
}

export interface StageTelemetry {
  status: RuntimeStatus;
  timeMs: number;
  durationMs: number;
  audioState: string;
  mouth: number;
  visemes: Visemes;
  emotions: Emotions;
  blink: number;
  blinks: number;
  camera: CameraPresetName;
  cuts: CutRecord[];
  wordIndex: number;
  word: string | null;
  avatar: AvatarCapabilities | null;
  avatarFallback: string | null;
  mouthSource: 'plan' | 'phonetic' | 'analyser' | 'none';
  frames: number;
  fps: number;
}

const ZERO_VIS: Visemes = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
const ZERO_EMO: Emotions = { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 };

// ── Stage Runtime ─────────────────────────────────────────────────

export class StageRuntime {
  private scene: THREE.Scene;
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private set: StageSet;
  private gaze = new THREE.Object3D();

  private transport: Transport;
  private audioBus: AudioBus;
  private sfx: SfxSynth;
  private cameraDirector: CameraDirector;
  private eventConsumer: EventConsumer;
  private clockSink: ClockSink;

  private avatar: AvatarDriver | null = null;
  private avatarFallback: string | null = null;
  private mouthAnchor: THREE.Object3D | null = null;
  private restMouth = new THREE.Vector3(0, 1.5, 0.1);
  private performer = new Performer();
  private face = new FaceChannel();
  private mouthTrack: MouthTrack | null = null;
  private prosodyTrack: ProsodyTrack | null = null;
  private analyserData: Uint8Array<ArrayBuffer>;

  private plan: PerformancePlan | null = null;
  private wordTimings: WordTiming[] = [];
  private cueIndex = 0;
  private camIndex = 0;

  private config: StageConfig;
  private frameId: number | null = null;
  private unbindKeyboard: (() => void) | null = null;
  private lastWall = 0;
  private resizeObserver: ResizeObserver | null = null;

  // telemetry
  private cuts: CutRecord[] = [];
  private mouthOpen = 0;
  private visemes: Visemes = { ...ZERO_VIS };
  private emotions: Emotions = { ...ZERO_EMO };
  private blink = 0;
  private blinks = 0;
  private wordIndex = -1;
  private frames = 0;
  private fps = 0;
  private fpsWindow: number[] = [];
  private captureTimeMs = 0;
  private lastCutSource: CutRecord['source'] = 'initial';

  status: RuntimeStatus = 'EMPTY';
  /** Resolves once an optional set variant (config.setVariant) has loaded or failed. */
  variantReady: Promise<void> = Promise.resolve();

  constructor(config: StageConfig) {
    this.config = config;
    this.clockSink = config.clockSink ?? NULL_CLOCK_SINK;
    const { clientWidth: w, clientHeight: h } = config.container;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(config.background || '#05030a');

    this.camera = new THREE.PerspectiveCamera(45, Math.max(1, w) / Math.max(1, h), 0.05, 60);

    const low = config.quality === 'low';
    this.renderer = new THREE.WebGLRenderer({ antialias: !low, alpha: false, preserveDrawingBuffer: !!config.capture });
    this.renderer.setPixelRatio(low ? 0.5 : Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(Math.max(1, w), Math.max(1, h));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.shadowMap.enabled = config.shadows ?? !low;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.style.display = 'block';
    config.container.appendChild(this.renderer.domElement);

    this.set = new StageSet(this.scene, { shadows: config.shadows ?? !low, sign: config.sign, lite: low });
    if (config.setVariant) {
      const v = COMEDY_CLUB.variants?.find((x) => x.id === config.setVariant);
      if (v) this.variantReady = this.set.loadVariant(v, config.resolveUrl);
      else this.set.variantStatus = `error:${config.setVariant}: unknown club set variant`;
    }
    this.gaze.position.set(0, 1.5, 6);
    this.scene.add(this.gaze);

    // Audio: transport → VOICE bus → analyser → MASTER (one graph).
    const audioContext = new AudioContext();
    this.transport = new Transport();
    this.transport.setAudioContext(audioContext);
    this.transport.setOnEnd(() => this.onTransportEnd());
    this.audioBus = new AudioBus(audioContext);
    this.transport.setOutputNode(this.audioBus.getGain('VOICE'));
    this.sfx = new SfxSynth(audioContext, this.audioBus.getGain('SFX'));
    this.analyserData = new Uint8Array(this.audioBus.getVoiceAnalyser().fftSize);
    if (config.capture) {
      this.transport.setManualClock(() => this.captureTimeMs);
      this.audioBus.muteAll();
    }

    this.cameraDirector = new CameraDirector(this.camera);
    this.cameraDirector.setAspect(this.camera.aspect);
    this.cameraDirector.setClock(() => this.transport.currentTimeMs);
    this.cameraDirector.setOnCut((camera, set_time_ms) => {
      this.cuts.push({ camera, set_time_ms: Math.round(set_time_ms), source: this.lastCutSource, wall_ms: Date.now() });
    });
    this.cuts.push({ camera: 'WIDE_STAGE', set_time_ms: 0, source: 'initial', wall_ms: Date.now() });
    if (config.keyboard) this.unbindKeyboard = this.cameraDirector.bindKeyboard();

    this.eventConsumer = new EventConsumer({ transport: config.transport, store: config.store });

    window.addEventListener('resize', this.handleResize);
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(this.handleResize);
      this.resizeObserver.observe(config.container);
    }

    // Idle performer before any show: BASIC body so the stage is never empty.
    void this.setAvatar({ avatarUrl: 'basic', name: 'house' }).then(() => {
      if (this.disposed) return;
      if (!config.capture) this.startLoop();
      else this.renderFrame(0, 1 / 30);
    });
  }

  // ── accessors ────────────────────────────────────────────────────
  get consumer(): EventConsumer { return this.eventConsumer; }
  get audio(): AudioBus { return this.audioBus; }
  get director(): CameraDirector { return this.cameraDirector; }
  get currentTimeMs(): number { return this.transport.currentTimeMs; }
  get canvas(): HTMLCanvasElement { return this.renderer.domElement; }
  get currentPlan(): PerformancePlan | null { return this.plan; }

  private handleResize = (): void => {
    const w = this.config.container.clientWidth;
    const h = this.config.container.clientHeight;
    if (!w || !h) return;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.cameraDirector.setAspect(this.camera.aspect);
    this.renderer.setSize(w, h);
  };

  // ── assets ───────────────────────────────────────────────────────

  private async setAvatar(spec: { avatarUrl: string; name?: string; seed?: string }): Promise<void> {
    const loaded = await loadAvatar({ url: spec.avatarUrl, name: spec.name, seed: spec.seed, lite: this.config.quality === 'low', cpuSkinning: this.config.cpuSkinning });
    if (this.disposed) { loaded.driver.dispose(); return; }
    if (this.avatar) this.avatar.dispose();
    this.avatar = loaded.driver;
    this.avatarFallback = loaded.fallbackReason ?? null;
    if (loaded.fallbackReason) console.warn('[stage]', loaded.fallbackReason);
    this.avatar.setGazeTarget(this.gaze);
    this.scene.add(this.avatar.root);
    this.fitMicToAvatar();
  }

  /** Stand-up: the mic goes in front of this body's mouth; the performer works it. */
  private fitMicToAvatar(): void {
    const anchor = this.avatar?.mouthAnchor?.() ?? null;
    this.mouthAnchor = anchor;
    this.performer.micMode = true;
    if (!anchor) return;
    this.avatar!.root.updateMatrixWorld(true);
    const mouth = anchor.getWorldPosition(new THREE.Vector3());
    this.restMouth.copy(mouth);
    this.set.fitMic(mouth);
  }

  /** Mic ↔ mouth geometry in metres (e2e + framing checks). */
  micReport(): { mouth: number[]; mic: number[]; distance: number; restMouth: number[]; avatar: string | null } {
    const mic = this.set.mic.grilleWorld();
    const mouth = this.mouthAnchor ? this.mouthAnchor.getWorldPosition(new THREE.Vector3()) : this.restMouth.clone();
    const r = (v: THREE.Vector3) => [v.x, v.y, v.z].map((x) => Math.round(x * 1000) / 1000);
    return { mouth: r(mouth), mic: r(mic), distance: Math.round(mic.distanceTo(mouth) * 1000) / 1000, restMouth: r(this.restMouth), avatar: this.avatar?.caps.kind ?? null };
  }

  async loadAudio(url: string): Promise<void> { await this.transport.loadAudio(url); }
  async loadAudioFromBytes(bytes: ArrayBuffer): Promise<void> { await this.transport.loadAudioFromBytes(bytes); }

  async unlockAudio(): Promise<void> {
    const ctx = this.transport.getAudioContext();
    if (ctx && ctx.state === 'suspended') await ctx.resume();
  }

  isAudioLocked(): boolean {
    const ctx = this.transport.getAudioContext();
    return !this.config.capture && !!ctx && ctx.state === 'suspended';
  }

  setPlan(plan: PerformancePlan, wordTimings: WordTiming[] = [], phonemes?: PhoneticViseme[], aus?: ProsodyFrame[]): void {
    this.plan = plan;
    this.wordTimings = wordTimings.length ? wordTimings : plan.word_timings ?? [];
    const planPhonemes = (plan as unknown as { visemes?: { visemes: string[]; vtimes: number[]; vdurations: number[] } }).visemes;
    const pv = phonemes ?? (planPhonemes ? toPhonetics(planPhonemes) : undefined);
    this.mouthTrack = MouthTrack.fromPlan(plan, this.wordTimings, pv);
    const planAus = (plan as unknown as { aus?: { frames: ProsodyFrame[] } }).aus;
    this.prosodyTrack = new ProsodyTrack(aus ?? planAus?.frames);
    this.performer.energy = plan.energy ?? 0.7;
    this.cueIndex = 0;
    this.camIndex = 0;
  }

  /** Load a performance: avatar + set audio + plan. EMPTY → LOADING → READY. */
  async preload(spec: PreloadSpec): Promise<void> {
    this.setStatus('LOADING');
    this.transport.stop();
    await Promise.all([
      this.setAvatar({ avatarUrl: spec.avatarUrl, name: spec.name, seed: spec.seed ?? spec.plan?.character_id }),
      this.loadAudio(spec.audioUrl),
    ]);
    this.setPlan(
      spec.plan,
      spec.wordTimings ?? [],
      spec.visemes ? toPhonetics(spec.visemes) : undefined,
      spec.aus?.frames,
    );
    this.performer.reset();
    this.cutCamera('WIDE_STAGE', 'auto_director');
    this.setStatus('READY');
  }

  private statusListeners = new Set<(s: RuntimeStatus) => void>();
  onStatus(cb: (s: RuntimeStatus) => void): () => void {
    this.statusListeners.add(cb);
    return () => { this.statusListeners.delete(cb); };
  }
  private setStatus(s: RuntimeStatus): void {
    this.status = s;
    for (const cb of this.statusListeners) { try { cb(s); } catch { /* never break playback */ } }
  }

  // ── transport (state-machine gated) ──────────────────────────────

  play(): void {
    if (this.status !== 'READY' && this.status !== 'PAUSED' && this.status !== 'ENDED') return;
    if (this.status === 'ENDED') { this.transport.stop(); this.cueIndex = 0; this.camIndex = 0; }
    if (!this.config.capture) this.transport.play();
    this.setStatus('PLAYING');
  }

  /** Start from an offset (late-joining stage catching up on a running set). */
  playFrom(ms: number): void {
    if (this.status !== 'READY' && this.status !== 'PAUSED') return;
    this.transport.seek(ms);
    this.syncIndices(ms);
    this.play();
  }

  pause(): void {
    if (this.status !== 'PLAYING') return;
    this.transport.pause();
    this.setStatus('PAUSED');
  }

  resume(): void {
    if (this.status !== 'PAUSED') return;
    this.play();
  }

  /** performance.end / show.end: stop the set, close the mouth. */
  end(): void {
    if (this.status === 'PLAYING' || this.status === 'PAUSED') {
      this.transport.pause();
      this.setStatus('ENDED');
    }
  }

  seek(ms: number): void {
    if (this.status !== 'PLAYING' && this.status !== 'PAUSED') return;
    this.transport.seek(ms);
    this.syncIndices(ms);
  }

  private syncIndices(ms: number): void {
    const cues = this.plan?.cues ?? [];
    const cams = this.plan?.camera_cues ?? [];
    this.cueIndex = Math.max(0, cues.findIndex((c) => c.at_ms >= ms));
    if (cues.length && cues[cues.length - 1].at_ms < ms) this.cueIndex = cues.length;
    let ci = 0;
    while (ci < cams.length && cams[ci].at_ms <= ms) ci++;
    if (ci > 0) { this.lastCutSource = 'auto_director'; this.cameraDirector.cut(cams[ci - 1].camera); }
    this.camIndex = ci;
  }

  private onTransportEnd(): void {
    this.setStatus('ENDED');
    this.cutCamera('WIDE_STAGE', 'auto_director');
  }

  // ── camera / reactions ───────────────────────────────────────────

  cutCamera(preset: CameraPresetName, source: CutRecord['source'] = 'human_director'): void {
    this.lastCutSource = source;
    this.cameraDirector.cut(preset);
  }

  async lookAtAudience(): Promise<void> {
    this.performer.trigger('gaze.audience', 1, 1000, this.performerClock());
  }

  /** Crowd reaction (crowd.reaction event): sound + room + performer. */
  react(kind: string): void {
    this.sfx.play(kind);
    const big = kind === 'laugh' || kind === 'clap' || kind === 'love';
    this.set.excite(big ? 1 : 0.3);
    const map: Record<string, string> = {
      laugh: 'reaction.laugh', clap: 'reaction.laugh', love: 'reaction.laugh',
      boo: 'reaction.boo', groan: 'reaction.groan', crickets: 'reaction.dead_stare', wtf: 'reaction.confused',
    };
    const action = map[kind];
    if (action) this.performer.trigger(action, 1, 1800, this.performerClock());
  }

  playSfx(name: string): void { this.sfx.play(name); }

  // ── face (face.expression / face.blendshapes / face.affect) ─────────
  faceExpression(emotionOrAction: string, intensity = 0.9, durationMs = 2000): boolean {
    const action = emotionToFaceAction(emotionOrAction);
    if (!action) return false;
    this.performer.trigger(action, intensity, durationMs, this.performerClock());
    return true;
  }
  faceBlendshapes(weights: Record<string, number>): void { this.face.setBlendshapes(weights, performance.now()); }
  faceAffect(a: number, v: number, p = 0, holdMs = 4000): void { this.face.setAffect(a, v, p, performance.now(), holdMs); }
  get faceSources(): string[] { return [...this.face.sources]; }

  duckMusic(): void { this.audioBus.duckMusic(); }
  unduckMusic(): void { this.audioBus.unduckMusic(); }

  async connect(episodeId: string, token?: string): Promise<void> {
    await this.eventConsumer.connect(episodeId, { role: 'stage', token });
  }

  // ── frame loop ───────────────────────────────────────────────────

  private performerClock(): number {
    return this.plan && this.status !== 'READY' && this.status !== 'LOADING' && this.status !== 'EMPTY'
      ? this.transport.currentTimeMs
      : performance.now();
  }

  private startLoop(): void {
    if (this.frameId !== null) return;
    this.lastWall = performance.now();
    const tick = () => {
      if (this.disposed) return;
      const now = performance.now();
      const dt = Math.min(0.1, (now - this.lastWall) / 1000);
      this.lastWall = now;
      this.renderFrame(now, dt);
      this.frameId = requestAnimationFrame(tick);
    };
    this.frameId = requestAnimationFrame(tick);
  }

  private renderFrame(wallMs: number, dt: number): void {
    const playing = this.status === 'PLAYING';
    const t = this.transport.currentTimeMs;
    if (playing) this.processCues(t);

    // mouth: plan track on the media clock, analyser as live fallback
    let open = 0;
    let vis: Visemes = { ...ZERO_VIS };
    if (playing && this.mouthTrack) {
      const s = this.mouthTrack.sample(t);
      open = s.open; vis = s.visemes; this.wordIndex = s.wordIndex;
    } else if (playing) {
      const an = this.audioBus.getVoiceAnalyser();
      an.getByteTimeDomainData(this.analyserData);
      let sum = 0;
      for (let i = 0; i < this.analyserData.length; i++) { const v = (this.analyserData[i] - 128) / 128; sum += v * v; }
      open = Math.min(1, Math.sqrt(sum / this.analyserData.length) * 5);
      vis = { ...ZERO_VIS, aa: open };
    }
    // smooth closing so pauses don't snap
    this.mouthOpen = open > this.mouthOpen ? open : this.mouthOpen + (open - this.mouthOpen) * Math.min(1, dt * 18);
    this.visemes = vis;

    const frame = this.performer.update(this.performerClock(), wallMs, dt, this.mouthOpen);
    this.emotions = frame.emotions;
    // AU prosody (aus.json): brows/eyes lift under beats; phrase blinks
    // OR with the Performer's own blink timer (speech-synced wins ties).
    const pro = playing && this.prosodyTrack ? this.prosodyTrack.sample(t) : null;
    this.blinks = this.performer.blinkCount;
    this.blink = Math.max(frame.blink, pro?.blink ?? 0);
    const face = this.face.sample(wallMs, { open: this.mouthOpen, visemes: vis, emotions: frame.emotions, blink: this.blink });
    this.emotions = face.emotions;
    if (this.avatar) {
      this.avatar.setPose(frame.pose);
      FaceChannel.apply(this.avatar, face);
      if (pro) this.avatar.setExpression(this.emotions, { brow: pro.brow, eye: pro.eye });
      this.avatar.update(dt);
    }
    this.gaze.position.set(frame.pose.headYaw * 4, 1.5 - frame.pose.headPitch * 4, 6);

    this.set.update(dt, wallMs);
    this.cameraDirector.update(wallMs, this.config.capture ? 0.5 : 1);
    this.clockSink.setCurrentTime(t);
    this.renderer.render(this.scene, this.camera);

    this.frames++;
    this.fpsWindow.push(wallMs);
    while (this.fpsWindow.length && wallMs - this.fpsWindow[0] > 1000) this.fpsWindow.shift();
    this.fps = this.fpsWindow.length;
  }

  private processCues(t: number): void {
    const plan = this.plan;
    if (!plan) return;
    while (this.cueIndex < plan.cues.length && plan.cues[this.cueIndex].at_ms <= t) {
      this.executeCue(plan.cues[this.cueIndex]);
      this.cueIndex++;
    }
    const cams: CameraCue[] = plan.camera_cues ?? [];
    while (this.camIndex < cams.length && cams[this.camIndex].at_ms <= t) {
      this.cutCamera(cams[this.camIndex].camera, 'auto_director');
      this.camIndex++;
    }
  }

  private executeCue(cue: MotionCue): void {
    this.performer.trigger(cue.action, cue.intensity, cue.duration_ms, cue.at_ms);
  }

  // ── capture (frame-stepped, offline MP4) ─────────────────────────

  /** Render the performance at media time `ms` and return a PNG data URL. */
  captureAt(ms: number, fps = 25): string {
    if (!this.config.capture) throw new Error('captureAt needs capture mode');
    if (this.status === 'READY') this.play();
    if (ms < this.captureTimeMs) { this.performer.reset(); this.syncIndices(ms); }
    this.captureTimeMs = ms;
    this.renderFrame(ms, 1 / fps);
    return this.renderer.domElement.toDataURL('image/jpeg', 0.9);
  }

  // ── telemetry ────────────────────────────────────────────────────

  private currentWordCb?: (index: number, word: string) => void;
  setWordCallback(cb: (index: number, word: string) => void): void { this.currentWordCb = cb; }

  /** Which comedy-club environment is showing ('procedural', a variant id, 'loading:…' or 'error:…'). */
  setVariantStatus(): string { return this.set.variantStatus; }

  telemetry(): StageTelemetry {
    const w = this.wordIndex >= 0 ? this.wordTimings[this.wordIndex] : undefined;
    if (w) this.currentWordCb?.(this.wordIndex, w.word);
    return {
      status: this.status,
      timeMs: Math.round(this.transport.currentTimeMs),
      durationMs: Math.round(this.transport.durationMs || this.plan?.duration_ms || 0),
      audioState: this.transport.getAudioContext()?.state ?? 'none',
      mouth: Math.round(this.mouthOpen * 1000) / 1000,
      visemes: { ...this.visemes },
      emotions: { ...this.emotions },
      blink: Math.round(this.blink * 1000) / 1000,
      blinks: this.blinks,
      camera: this.cameraDirector.getCurrentPreset(),
      cuts: [...this.cuts],
      wordIndex: this.wordIndex,
      word: w?.word ?? null,
      avatar: this.avatar?.caps ?? null,
      avatarFallback: this.avatarFallback,
      mouthSource: this.mouthTrack?.hasPhonetics ? 'phonetic' : this.mouthTrack ? 'plan' : this.avatar?.caps.mouthMode === 'none' ? 'none' : 'analyser',
      frames: this.frames,
      fps: this.fps,
    };
  }

  // ── cleanup ──────────────────────────────────────────────────────

  private disposed = false;

  dispose(): void {
    this.disposed = true;
    if (this.frameId !== null) cancelAnimationFrame(this.frameId);
    this.frameId = null;
    window.removeEventListener('resize', this.handleResize);
    this.resizeObserver?.disconnect();
    this.unbindKeyboard?.();
    this.transport.dispose();
    this.audioBus.dispose();
    this.cameraDirector.dispose();
    this.eventConsumer.disconnect();
    this.avatar?.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
    void this.transport.getAudioContext()?.close().catch(() => {});
  }
}
