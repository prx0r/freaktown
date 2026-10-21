/**
 * SetStage — the multi-seat renderer for sets (news studio, podcast, poker,
 * and the comedy club as a one-seat set). One scene, N seated/standing
 * characters, seat-aware cameras, an active-speaker auto director, DOM
 * overlay state, and poker props. Obeys SetEventExecutor; never talks to
 * control directly.
 *
 *   loadSet(id, cast)  build the set (procedural; optional CC0 GLB decor)
 *   cast(members)      characters into seats (BASIC / VRM / GLB via loadAvatar)
 *   say(line)          speaker mouth (text-timed, or audio) + gestures + auto cut
 *   cut(cue)           "wide" | preset | close:<seat> | two-shot:a+b | orbit …
 *   poker(type, p)     cards / chips / button / reactions
 *   theme(p)           set.theme show style (lighting tint, wall painter theme)
 *   renderAt(ms)       deterministic frame for show time ms (config.manual: no RAF)
 */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { CastMemberV1, CardV1, DialogueLinePayloadV1, HeadlinePayloadV1, SetThemePayloadV1 } from '@freaktown/contracts';
import type { SetDefinition, SeatAnchor } from './types';
import { SET_REGISTRY, SetRegistry, findSeat } from './registry';
import { resolveCameraCue, seatForward, seatHead, seatSide, type CameraShot } from './camera';
import { ActiveSpeakerDirector } from './autoDirector';
import { estimateLineMs, textMouth } from './textMouth';
import { SET_BUILDERS } from './builders/sets';
import type { BuiltSet, WallPainter } from './builders/common';
import { PokerProps } from './poker/PokerProps';
import { loadAvatar } from '../avatars/loadAvatar';
import type { AvatarDriver, AvatarCapabilities } from '../avatars/types';
import { Performer } from '../performance/Performer';
import { FaceChannel } from '../face/FaceChannel';
import { compileHarnessBeats } from '../face/harnessBeats';
import { emotionToFaceAction, HARNESS_SET_CAMERAS } from '../face/vocab';

export interface SetStageConfig {
  container: HTMLElement;
  quality?: 'high' | 'low';
  cpuSkinning?: boolean;
  /** Load unverified GLB decor (environment.glb) too. */
  glb?: boolean;
  registry?: SetRegistry;
  resolveUrl?: (url: string) => string;
  /**
   * Deterministic clock: no requestAnimationFrame loop; the host calls
   * renderAt(ms) and every timer inside the stage reads that show time.
   * Used by headless capture (newsroom render CLI). Default false.
   */
  manual?: boolean;
  /** Draws the video-wall card (newsroom). Sets without a wall ignore it. */
  wallPainter?: WallPainter;
}

/** An eased camera move / slow creep (set.camera move_ms / creep). */
export interface CameraMoveOptions { move_ms?: number; ease?: 'smooth' | 'linear'; creep?: number; creep_ms?: number }
interface CamPose { position: [number, number, number]; target: [number, number, number]; fov: number }

interface SeatActor {
  seat: SeatAnchor;
  index: number;
  member: CastMemberV1;
  holder: THREE.Group;
  driver: AvatarDriver;
  performer: Performer;
  speaking: { text: string; start: number; dur: number; audio?: HTMLAudioElement } | null;
  mouth: number;
  folded: boolean;
  face: FaceChannel;
  lastEmotions?: Record<string, number>;
}

export interface SetCut { cue: string; at_ms: number; source: 'auto_director' | 'human_director' | 'initial' }

export interface OverlayState {
  lowerThird: { name: string; title?: string } | null;
  ticker: string[];
  headline: ({ text: string; kicker?: string } & Partial<HeadlinePayloadV1>) | null;
  theme?: SetThemePayloadV1 | null;
  speaker: { seat: string; name: string; text: string } | null;
  onAir: boolean;
}

export interface PokerView {
  handId: string;
  pot: number;
  board: CardV1[];
  button: number;
  toAct: number | null;
  toCall: number;
  actions: string[];
  stacks: Record<number, number>;
  names: Record<number, string>;
  hole: Record<number, CardV1[]>;
  folded: number[];
  lastAction: { seat: number; action: string; amount: number } | null;
  history: Array<{ seat: number; action: string; amount: number }>;
  winners: Array<{ seat: number; amount: number; ranking: string }>;
  street: string;
}

export interface SetStageTelemetry {
  setId: string | null;
  setName: string | null;
  camera: string;
  cuts: SetCut[];
  autoDirector: boolean;
  seats: Array<{ seat: string; name: string; avatar: AvatarCapabilities['kind']; mouthMode: string; speaking: boolean; mouth: number; seated: boolean; emotions: Record<string, number>; faceSources: string[] }>;
  actingWarnings: string[];
  activeSpeaker: string | null;
  lines: number;
  environment: 'procedural' | 'procedural+glb';
  envError: string | null;
  overlay: OverlayState;
  poker: PokerView | null;
  props: { hole: number; board: number; pot: number } | null;
  frames: number;
  fps: number;
}

const emptyPoker = (): PokerView => ({
  handId: '', pot: 0, board: [], button: -1, toAct: null, toCall: 0, actions: [], stacks: {}, names: {}, hole: {},
  folded: [], lastAction: null, history: [], winners: [], street: 'preflop',
});

export class SetStage {
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private renderer: THREE.WebGLRenderer;
  private config: SetStageConfig;
  private registry: SetRegistry;
  private def: SetDefinition | null = null;
  private built: BuiltSet | null = null;
  private props: PokerProps | null = null;
  private actors = new Map<string, SeatActor>();
  private shot: CameraShot | null = null;
  private cueName = 'wide';
  private cuts: SetCut[] = [];
  private director = new ActiveSpeakerDirector();
  private auto = true;
  private manualNow = 0;
  private t0 = 0;
  private move: { from: CamPose; start: number; dur: number; ease: 'smooth' | 'linear' } | null = null;
  private creep: { k: number; start: number; dur: number } | null = null;
  private pose: CamPose | null = null;
  private themeP: SetThemePayloadV1 | null = null;
  private frameId: number | null = null;
  private last = 0;
  private frames = 0;
  private fpsWin: number[] = [];
  private disposed = false;
  private loadToken = 0;
  private envGlb: THREE.Object3D | null = null;
  private envError: string | null = null;
  private lines = 0;
  private actingWarnings: string[] = [];
  private aspect = 16 / 9;
  private resizeObs: ResizeObserver | null = null;
  overlay: OverlayState = { lowerThird: null, ticker: [], headline: null, speaker: null, onAir: true };
  pokerView: PokerView = emptyPoker();

  constructor(config: SetStageConfig) {
    this.config = config;
    this.t0 = this.nowMs();
    this.last = this.nowMs();
    this.registry = config.registry ?? SET_REGISTRY;
    const { clientWidth: w, clientHeight: h } = config.container;
    const low = config.quality === 'low';
    this.camera = new THREE.PerspectiveCamera(40, Math.max(1, w) / Math.max(1, h), 0.05, 80);
    this.renderer = new THREE.WebGLRenderer({ antialias: !low, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(low ? 0.5 : Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(Math.max(1, w), Math.max(1, h));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.shadowMap.enabled = !low;
    this.renderer.domElement.style.display = 'block';
    config.container.appendChild(this.renderer.domElement);
    this.handleResize();
    window.addEventListener('resize', this.handleResize);
    if (typeof ResizeObserver !== 'undefined') { this.resizeObs = new ResizeObserver(this.handleResize); this.resizeObs.observe(config.container); }
    if (!config.manual) this.startLoop();
  }

  /** Stage clock: performance.now(), or the host-driven show time in manual mode. */
  private nowMs(): number { return this.config.manual ? this.manualNow : performance.now(); }

  /**
   * Manual mode: advance the clock to show time ms and render exactly that frame.
   * Returns the canvas for capture. Safe to call in realtime mode too (renders an extra frame).
   */
  renderAt(ms: number): HTMLCanvasElement {
    const prev = this.manualNow;
    this.manualNow = ms;
    const dt = Math.max(0, Math.min(0.1, (ms - prev) / 1000));
    this.last = ms;
    this.renderFrame(this.nowMs(), dt);
    return this.renderer.domElement;
  }

  get canvas(): HTMLCanvasElement { return this.renderer.domElement; }
  get definition(): SetDefinition | null { return this.def; }
  /** Manual mode: move the clock without rendering (apply timed events at their own instant). */
  advanceClock(ms: number): void { if (this.config.manual) { this.manualNow = ms; this.last = ms; } }

  get setTimeMs(): number { return this.nowMs() - this.t0; }

  private handleResize = (): void => {
    const w = this.config.container.clientWidth, h = this.config.container.clientHeight;
    if (!w || !h) return;
    this.aspect = w / h;
    this.camera.aspect = this.aspect;
    this.renderer.setSize(w, h);
    this.applyShot();
  };

  // ── set + cast ─────────────────────────────────────────────────────

  async loadSet(setId: string, cast: CastMemberV1[] = []): Promise<void> {
    const def = this.registry.require(setId);
    const token = ++this.loadToken;
    this.clearSet();
    this.def = def;
    this.t0 = this.nowMs();
    this.move = null; this.creep = null; this.pose = null;
    this.scene.background = new THREE.Color(def.lighting.background);
    this.scene.fog = new THREE.Fog(def.lighting.background, 12, 40);
    const builder = SET_BUILDERS[def.environment.builder];
    if (!builder) throw new Error(`set ${def.id}: no builder "${def.environment.builder}"`);
    this.built = builder(def, { shadows: this.config.quality !== 'low', low: this.config.quality === 'low' });
    this.scene.add(this.built.group);
    if (def.id === 'poker-table') { this.props = new PokerProps(def); this.scene.add(this.props.group); }
    this.overlay = { lowerThird: null, ticker: [], headline: null, speaker: null, onAir: true, theme: null };
    this.themeP = null;
    if (this.config.wallPainter) this.built.setWallPainter?.(this.config.wallPainter);
    this.pokerView = emptyPoker();
    this.director = new ActiveSpeakerDirector({ wide: 'wide' });
    this.cuts = [];
    this.cut('wide', 'initial');
    const glb = def.environment.glb;
    if (glb && (glb.verified || this.config.glb)) void this.loadGlb(def, token);
    if (cast.length) await this.cast(cast);
  }

  private async loadGlb(def: SetDefinition, token: number): Promise<void> {
    const g = def.environment.glb!;
    try {
      const gltf = await new GLTFLoader().loadAsync(this.resolve(g.url));
      if (token !== this.loadToken || this.disposed) return;
      const root = gltf.scene;
      const tr = g.transform ?? {};
      if (tr.scale) root.scale.setScalar(tr.scale);
      if (tr.rotation) root.rotation.y = tr.rotation;
      if (tr.position) root.position.set(...tr.position);
      if (g.hideNodes?.length) root.traverse((o) => { if (g.hideNodes!.some((n) => o.name.includes(n))) o.visible = false; });
      this.envGlb = root;
      this.scene.add(root);
    } catch (e) {
      this.envError = `glb decor failed (${e instanceof Error ? e.message : String(e)}); procedural set only`;
      console.warn('[set]', this.envError);
    }
  }

  private resolve(u: string): string { return this.config.resolveUrl ? this.config.resolveUrl(u) : u; }

  private clearSet(): void {
    for (const a of this.actors.values()) { a.speaking?.audio?.pause(); a.driver.dispose(); a.holder.parent?.remove(a.holder); }
    this.actors.clear();
    this.built?.dispose();
    this.built = null;
    if (this.props) { this.scene.remove(this.props.group); this.props = null; }
    if (this.envGlb) { this.scene.remove(this.envGlb); this.envGlb = null; }
    this.envError = null;
    this.lines = 0;
  }

  async cast(members: CastMemberV1[]): Promise<void> {
    const def = this.def;
    if (!def) return;
    const token = this.loadToken;
    await Promise.all(members.map(async (m) => {
      const seat = findSeat(def, m.seat);
      if (!seat) { console.warn('[set] no seat', m.seat); return; }
      const loaded = await loadAvatar({
        url: !m.avatar_url || m.avatar_url.startsWith('basic') ? (m.avatar_url || 'basic') : this.resolve(m.avatar_url),
        name: m.name, seed: m.character_id,
        lite: this.config.quality === 'low', cpuSkinning: this.config.cpuSkinning,
      });
      if (token !== this.loadToken || this.disposed) { loaded.driver.dispose(); return; }
      const prev = this.actors.get(seat.id);
      if (prev) { prev.driver.dispose(); prev.holder.parent?.remove(prev.holder); }
      const holder = new THREE.Group();
      holder.position.set(...seat.position);
      holder.rotation.y = seat.rotation;
      holder.add(loaded.driver.root);
      loaded.driver.setSeated?.(seat.pose === 'seated');
      const gaze = new THREE.Object3D();
      this.scene.add(gaze);
      loaded.driver.setGazeTarget(gaze);
      holder.userData.gaze = gaze;
      this.scene.add(holder);
      const performer = new Performer();
      performer.energy = 0.5;
      this.actors.set(seat.id, {
        seat, index: def.seats.indexOf(seat), member: m, holder, driver: loaded.driver, performer,
        speaking: null, mouth: 0, folded: false, face: new FaceChannel(),
      });
      const pi = def.seats.indexOf(seat);
      this.pokerView.names[pi] = m.name;
    }));
  }

  actorAtIndex(i: number): SeatActor | undefined {
    for (const a of this.actors.values()) if (a.index === i) return a;
    return undefined;
  }

  // ── dialogue ──────────────────────────────────────────────────────

  say(line: DialogueLinePayloadV1): void {
    const def = this.def;
    if (!def) return;
    const seat = findSeat(def, line.seat);
    const actor = seat ? this.actors.get(seat.id) : undefined;
    if (!seat || !actor) { console.warn('[set] line for empty seat', line.seat); return; }
    for (const a of this.actors.values()) if (a !== actor && a.speaking) { a.speaking.audio?.pause(); a.speaking = null; }
    const dur = line.duration_ms ?? estimateLineMs(line.text);
    let audio: HTMLAudioElement | undefined;
    if (line.audio_url) { audio = new Audio(this.resolve(line.audio_url)); void audio.play().catch(() => {}); }
    const now = this.nowMs();
    actor.speaking = { text: line.text, start: now, dur, audio };
    this.lines++;
    const emo = line.emotion ? emotionToFaceAction(line.emotion) : null;
    if (emo) actor.performer.trigger(emo, 0.9, dur, now);
    actor.performer.trigger(line.cue ?? (this.lines % 2 ? 'gesture.open' : emo ? 'gesture.open' : 'face.smile'), 0.8, Math.min(dur, 2200), now);
    if (this.lines % 3 === 0) actor.performer.trigger('gesture.point', 0.6, 1200, now + 300);
    let actedCamera = false;
    if (line.beats?.length) {
      if (!line.words?.length) this.actingWarnings.push(`line on ${seat.id}: beats ignored without measured words`);
      else {
        try {
          const acted = compileHarnessBeats(line.text, line.beats, line.words, { humanoid: actor.driver.caps.hasSkeleton || actor.driver.caps.kind === 'basic' });
          for (const m of acted.motion) actor.performer.trigger(m.action, m.intensity, m.duration_ms, now + m.at_ms);
          const camBeats = line.beats.filter((x) => x.camera && HARNESS_SET_CAMERAS[x.camera.toLowerCase()]);
          acted.camera.forEach((c, i) => {
            const mk = camBeats[i] && HARNESS_SET_CAMERAS[camBeats[i].camera!.toLowerCase()];
            if (!mk) return;
            setTimeout(() => this.cut(mk(seat.id), 'auto_director'), c.at_ms);
            actedCamera = true;
          });
          this.actingWarnings.push(...acted.warnings);
        } catch (e) {
          this.actingWarnings.push(`acting rejected: ${e instanceof Error ? e.message : String(e)}`);
        }
      }
    }
    this.overlay.speaker = { seat: seat.id, name: actor.member.name, text: line.text };
    if (this.auto && !actedCamera) {
      const cue = this.director.onLine(seat.id, this.setTimeMs, dur);
      if (cue) this.cut(cue, 'auto_director');
    }
  }

  // ── face (face.expression / face.blendshapes / face.affect) ─────────

  private actorFor(ref?: string): SeatActor | undefined {
    if (!this.def) return undefined;
    const seat = ref ? findSeat(this.def, ref) : this.def.seats[0];
    return seat ? this.actors.get(seat.id) : undefined;
  }
  faceExpression(p: { seat?: string; emotion?: string; action?: string; intensity?: number; duration_ms?: number }): boolean {
    const a = this.actorFor(p.seat);
    const action = p.action ?? (p.emotion ? emotionToFaceAction(p.emotion) : null);
    if (!a || !action) return false;
    a.performer.trigger(action, p.intensity ?? 0.9, p.duration_ms ?? 2000, this.nowMs());
    return true;
  }
  faceBlendshapes(seat: string | undefined, weights: Record<string, number>): boolean {
    const a = this.actorFor(seat);
    if (!a) return false;
    a.face.setBlendshapes(weights, this.nowMs());
    return true;
  }
  faceAffect(p: { seat?: string; a: number; v: number; p?: number; hold_ms?: number }): boolean {
    const a = this.actorFor(p.seat);
    if (!a) return false;
    a.face.setAffect(p.a, p.v, p.p ?? 0, this.nowMs(), p.hold_ms ?? 4000);
    return true;
  }

  // ── camera ────────────────────────────────────────────────────────

  setAutoDirector(on: boolean): void { this.auto = on; }

  cut(cue: string, source: SetCut['source'] = 'human_director', opts: CameraMoveOptions = {}): boolean {
    const def = this.def;
    if (!def) return false;
    if (cue === 'auto') { this.auto = true; return true; }
    try {
      this.shot = resolveCameraCue(def, cue, this.setTimeMs / 1000);
    } catch (e) {
      console.warn('[set]', e instanceof Error ? e.message : e);
      return false;
    }
    const now = this.nowMs();
    this.move = opts.move_ms && opts.move_ms > 0 && this.pose ? { from: this.pose, start: now, dur: opts.move_ms, ease: opts.ease ?? 'smooth' } : null;
    const k = Math.max(0, Math.min(0.3, opts.creep ?? 0));
    this.creep = k > 0 ? { k, start: now + (opts.move_ms ?? 0), dur: Math.max(1000, opts.creep_ms ?? 12000) } : null;
    this.cueName = cue;
    this.director.note(cue, this.setTimeMs);
    this.cuts.push({ cue, at_ms: Math.round(this.setTimeMs), source });
    this.applyShot();
    return true;
  }

  /** Current camera pose: shot, eased from the previous pose during a move, plus creep. */
  private portraitFov = false;
  private currentPose(): CamPose | null {
    let s = this.shot;
    if (!s) return null;
    const portrait = this.aspect < 1 ? this.def?.cameras[this.cueName]?.portrait : undefined;
    this.portraitFov = !!portrait;
    if (portrait) s = { ...s, position: portrait.position, target: portrait.target, fov: portrait.fov };
    const now = this.nowMs();
    let pos: [number, number, number] = [...s.position];
    let tgt: [number, number, number] = [...s.target];
    let fov = s.fov;
    if (this.creep) {
      const u = Math.max(0, Math.min(1, (now - this.creep.start) / this.creep.dur));
      const e = 0.5 - 0.5 * Math.cos(Math.PI * u);
      const k = this.creep.k * e;
      pos = [pos[0] + (tgt[0] - pos[0]) * k, pos[1] + (tgt[1] - pos[1]) * k, pos[2] + (tgt[2] - pos[2]) * k];
    }
    if (this.move) {
      const u = Math.max(0, Math.min(1, (now - this.move.start) / this.move.dur));
      const e = this.move.ease === 'linear' ? u : 0.5 - 0.5 * Math.cos(Math.PI * u);
      const f = this.move.from;
      const L = (a: number, b: number) => a + (b - a) * e;
      pos = [L(f.position[0], pos[0]), L(f.position[1], pos[1]), L(f.position[2], pos[2])];
      tgt = [L(f.target[0], tgt[0]), L(f.target[1], tgt[1]), L(f.target[2], tgt[2])];
      fov = L(f.fov, fov);
      if (u >= 1) this.move = null;
    }
    return { position: pos, target: tgt, fov };
  }

  private applyShot(): void {
    const s = this.currentPose();
    if (!s) return;
    this.pose = s;
    let fov = s.fov;
    if (this.aspect < 1.4 && !this.portraitFov) fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(fov) / 2) * Math.min(2.2, Math.sqrt(1.78 / this.aspect))));
    this.camera.fov = Math.min(80, fov);
    this.camera.position.set(...s.position);
    this.camera.lookAt(...s.target);
    this.camera.updateProjectionMatrix();
  }

  // ── overlays ──────────────────────────────────────────────────────

  lowerThird(p: { name: string; title?: string; show?: boolean }): void { this.overlay.lowerThird = p.show === false ? null : { name: p.name, title: p.title }; }
  ticker(items: string[]): void { this.overlay.ticker = items; }
  headline(text: string, kicker?: string, card?: Partial<HeadlinePayloadV1>): void {
    this.overlay.headline = { ...(card ?? {}), text, kicker };
    if (this.built?.setWall && (this.config.wallPainter || card?.layout)) this.built.setWall({ ...(card ?? {}), text, kicker }, this.themeP);
    else this.built?.setHeadline?.(text, kicker);
  }

  /** set.theme: tint the lights/background and hand the theme to the wall painter. */
  theme(p: SetThemePayloadV1): void {
    this.themeP = p;
    this.overlay.theme = p;
    const L = p.lighting;
    if (L?.background) { this.scene.background = new THREE.Color(L.background); this.scene.fog = new THREE.Fog(L.background, 12, 40); }
    if (L?.exposure) this.renderer.toneMappingExposure = L.exposure;
    this.built?.setTheme?.(p);
    if (this.overlay.headline && this.built?.setWall) this.built.setWall(this.overlay.headline, p);
  }

  setWallPainter(painter: WallPainter): void { this.config.wallPainter = painter; this.built?.setWallPainter?.(painter); }

  // ── poker ─────────────────────────────────────────────────────────

  poker(type: string, p: Record<string, any>): void {
    const v = this.pokerView;
    const props = this.props;
    const react = (seat: number, action: string, k = 1, dur = 1400) => this.actorAtIndex(seat)?.performer.trigger(action, k, dur, this.nowMs());
    switch (type) {
      case 'poker.hand_start':
        props?.reset();
        Object.assign(v, emptyPoker(), { names: v.names });
        v.handId = p.hand_id; v.button = p.button;
        for (const s of p.seats ?? []) { v.stacks[s.seat] = s.stack; const a = this.actorAtIndex(s.seat); v.names[s.seat] = a ? a.member.name : (s.name ?? `seat ${s.seat}`); }
        for (const a of this.actors.values()) a.folded = false;
        props?.setButton(p.button);
        break;
      case 'poker.deal':
        v.hole[p.seat] = p.cards;
        props?.deal(p.seat, p.cards, false);
        break;
      case 'poker.turn':
        v.toAct = p.seat; v.toCall = p.to_call ?? 0; v.actions = p.actions ?? []; v.pot = p.pot ?? v.pot;
        break;
      case 'poker.action': {
        v.lastAction = { seat: p.seat, action: p.action, amount: p.amount };
        v.history = [...v.history, v.lastAction];
        v.stacks[p.seat] = p.stack; v.pot = p.pot; v.street = p.street; v.toAct = null;
        if (p.action === 'fold') { v.folded.push(p.seat); props?.fold(p.seat); const a = this.actorAtIndex(p.seat); if (a) a.folded = true; react(p.seat, 'pose.lean_back', 1, 1800); react(p.seat, 'face.annoyed', 0.7, 1600); }
        else if (p.action === 'raise' || p.action === 'bet') { react(p.seat, 'gesture.point', 1, 1200); react(p.seat, 'face.smug', 0.9, 1800); }
        else if (p.action === 'call') react(p.seat, 'gesture.open', 0.6, 1000);
        else react(p.seat, 'pose.lean_forward', 0.5, 900);
        break;
      }
      case 'poker.chips':
        props?.chips(p.from, p.to, p.amount);
        break;
      case 'poker.board':
        v.board = p.cards; v.street = p.street;
        props?.setBoard(p.cards);
        for (const a of this.actors.values()) if (!a.folded) a.performer.trigger('pose.lean_forward', 0.6, 1200, this.nowMs());
        break;
      case 'poker.showdown': {
        v.winners = (p.winners ?? []).map((w: any) => ({ seat: w.seat, amount: w.amount, ranking: w.ranking }));
        v.toAct = null;
        for (const h of p.hole ?? []) { v.hole[h.seat] = h.cards; props?.reveal(h.seat, h.cards); }
        const winners = new Set(v.winners.map((w) => w.seat));
        for (const a of this.actors.values()) {
          if (winners.has(a.index)) { react(a.index, 'reaction.laugh', 1, 2500); react(a.index, 'gesture.wave', 1, 1800); }
          else if (!a.folded) react(a.index, 'face.annoyed', 0.8, 2200);
        }
        for (const w of v.winners) v.stacks[w.seat] = (v.stacks[w.seat] ?? 0) + w.amount;
        v.pot = 0;
        break;
      }
    }
  }

  // ── frame loop ────────────────────────────────────────────────────

  private startLoop(): void {
    const tick = () => {
      if (this.disposed) return;
      const now = performance.now();
      const dt = Math.min(0.1, (now - this.last) / 1000);
      this.last = now;
      this.renderFrame(now, dt);
      this.frameId = requestAnimationFrame(tick);
    };
    this.frameId = requestAnimationFrame(tick);
  }

  private renderFrame(now: number, dt: number): void {
    let speaker: SeatActor | null = null;
    for (const a of this.actors.values()) {
      let open = 0;
      let vis = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
      if (a.speaking) {
        const t = now - a.speaking.start;
        if (t > a.speaking.dur) a.speaking = null;
        else { const s = textMouth(a.speaking.text, a.speaking.dur, t); open = s.open; vis = s.visemes; speaker = a; }
      }
      a.mouth = open > a.mouth ? open : a.mouth + (open - a.mouth) * Math.min(1, dt * 18);
      const frame = a.performer.update(now, now, dt, a.mouth);
      const pose = frame.pose;
      // listeners turn their heads to the speaker; speakers address the room/camera
      const target = speaker && speaker !== a ? speaker : this.lastSpeaker && this.lastSpeaker !== a ? this.lastSpeaker : null;
      if (target) {
        const h = seatHead(target.seat), me = seatHead(a.seat);
        const d: [number, number, number] = [h[0] - me[0], 0, h[2] - me[2]];
        const f = seatForward(a.seat), sd = seatSide(a.seat);
        const ang = Math.atan2(d[0] * sd[0] + d[2] * sd[2], d[0] * f[0] + d[2] * f[2]);
        pose.headYaw += Math.max(-0.75, Math.min(0.75, ang)) * 0.8;
        const gz = a.holder.userData.gaze as THREE.Object3D | undefined;
        gz?.position.set(h[0], h[1], h[2]);
      } else {
        const gz = a.holder.userData.gaze as THREE.Object3D | undefined;
        if (gz) gz.position.set(this.camera.position.x, this.camera.position.y, this.camera.position.z);
      }
      if (a.seat.pose === 'seated') { pose.swayX *= 0.3; pose.bob *= 0.3; }
      a.driver.setPose(pose);
      const face = a.face.sample(now, { open: a.mouth, visemes: vis, emotions: frame.emotions, blink: frame.blink });
      a.lastEmotions = face.emotions;
      FaceChannel.apply(a.driver, face);
      a.driver.update(dt);
    }
    if (speaker) this.lastSpeaker = speaker;
    if (!speaker && this.overlay.speaker && this.actors.size) {
      // keep the strap up briefly after the line
    }
    if (this.auto && this.def) {
      const cue = this.director.tick(this.setTimeMs);
      if (cue) this.cut(cue, 'auto_director');
    }
    // orbit shots follow the clock
    if (this.def && this.shot && (this.cueName === 'orbit' || this.def.cameras[this.cueName]?.orbit)) {
      try { this.shot = resolveCameraCue(this.def, this.cueName, this.setTimeMs / 1000); this.applyShot(); } catch { /* keep */ }
    } else if (this.move || this.creep) this.applyShot();
    this.built?.update(dt, now);
    this.props?.update(dt);
    this.renderer.render(this.scene, this.camera);
    this.frames++;
    this.fpsWin.push(now);
    while (this.fpsWin.length && now - this.fpsWin[0] > 1000) this.fpsWin.shift();
  }
  private lastSpeaker: SeatActor | null = null;

  telemetry(): SetStageTelemetry {
    const speaking = [...this.actors.values()].find((a) => a.speaking);
    return {
      setId: this.def?.id ?? null,
      setName: this.def?.name ?? null,
      camera: this.cueName,
      cuts: [...this.cuts],
      autoDirector: this.auto,
      seats: [...this.actors.values()].map((a) => ({
        seat: a.seat.id, name: a.member.name, avatar: a.driver.caps.kind, mouthMode: a.driver.caps.mouthMode,
        speaking: !!a.speaking, mouth: Math.round(a.mouth * 1000) / 1000, seated: a.seat.pose === 'seated',
        emotions: Object.fromEntries(Object.entries(a.lastEmotions ?? {}).map(([k, v]) => [k, Math.round(v * 100) / 100])), faceSources: [...a.face.sources],
      })),
      activeSpeaker: speaking?.seat.id ?? null,
      lines: this.lines,
      actingWarnings: this.actingWarnings.slice(-10),
      environment: this.envGlb ? 'procedural+glb' : 'procedural',
      envError: this.envError,
      overlay: { ...this.overlay },
      poker: this.def?.id === 'poker-table' ? { ...this.pokerView } : null,
      props: this.props?.counts ?? null,
      frames: this.frames,
      fps: this.fpsWin.length,
    };
  }

  dispose(): void {
    this.disposed = true;
    if (this.frameId !== null) cancelAnimationFrame(this.frameId);
    window.removeEventListener('resize', this.handleResize);
    this.resizeObs?.disconnect();
    this.clearSet();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
