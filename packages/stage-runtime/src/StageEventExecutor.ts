/**
 * StageEventExecutor — the execution layer. The stage obeys events only.
 *
 *   performance.preload → runtime.preload() → stage.ack performance.ready
 *   performance.start   → runtime.play()   (READY only — gated)
 *   performance.pause / show.pause   → runtime.pause()
 *   performance.resume / show.resume → runtime.resume()
 *   performance.end / show.end       → runtime.end()
 *   camera.cut          → runtime.cutCamera()      (human director)
 *   crowd.reaction      → runtime.react(kind)      (sfx + room + performer)
 *   audio.music.play/stop, audio.sfx.play
 *   character.enter     → gaze to audience
 *   character.exit      → runtime.end()
 *
 * Events execute strictly in seq order through one promise queue, so a
 * replayed log (late join / reload) can't start a set before its preload
 * resolved. The ready ACK is skipped when the log already holds one for
 * that performance (replay never duplicates ACKs).
 */

import { CAMERA_NAMES, type CameraPresetV1, type PerformancePlan, type ShowEvent } from '@freaktown/contracts';
import type { StageRuntime } from './StageRuntime';
import type { EventConsumer } from './EventConsumer';
import { loadSealedSet } from './plan/setAdapter';

export interface ExecutorOptions {
  /** Resolve asset keys/URLs. SFX names map to URLs here (else synth). */
  sfxUrl?: (name: string) => string | null;
  /** Resolve relative asset URLs from events (e.g. app base path). */
  resolveUrl?: (url: string) => string;
  onError?: (message: string) => void;
  /** Late-join catch-up threshold: a performance.start older than this seeks. */
  catchUpAfterMs?: number;
  now?: () => number;
}

export class StageEventExecutor {
  private runtime: StageRuntime;
  private consumer: EventConsumer;
  private opts: ExecutorOptions;
  private unsubscribe: (() => void) | null = null;
  private musicSource: AudioBufferSourceNode | null = null;
  private queue: Promise<void> = Promise.resolve();
  private readySeen = new Set<string>();
  readonly executed: Array<{ seq: number; type: string }> = [];

  constructor(runtime: StageRuntime, consumer: EventConsumer, opts: ExecutorOptions = {}) {
    this.runtime = runtime;
    this.consumer = consumer;
    this.opts = opts;
  }

  attach(): void {
    this.unsubscribe = this.consumer.onEvent((event) => {
      if (event.type === 'performance.ready' && typeof event.payload?.performance_id === 'string') {
        this.readySeen.add(event.payload.performance_id);
      }
      this.queue = this.queue
        .then(() => this.execute(event))
        .catch((e: unknown) => this.opts.onError?.(e instanceof Error ? e.message : String(e)));
    });
  }

  detach(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  /** Resolves when every event received so far has executed. */
  idle(): Promise<void> { return this.queue; }

  private url(u: string): string { return this.opts.resolveUrl ? this.opts.resolveUrl(u) : u; }

  async execute(event: ShowEvent): Promise<void> {
    const payload = event.payload ?? {};
    this.executed.push({ seq: event.seq, type: event.type });
    switch (event.type) {
      case 'performance.preload': {
        const avatarUrl = (payload.avatar_url as string) ?? 'basic';
        const audioUrl = payload.audio_url as string;
        if (!audioUrl) throw new Error('performance.preload missing audio_url');
        let plan = payload.plan as PerformancePlan | undefined;
        if (!plan && typeof payload.set_url === 'string') {
          // Sealed set dir (build_set.py outputs) adapted on the stage.
          plan = await loadSealedSet(this.url(payload.set_url), {
            appearanceId: payload.performance_id as string | undefined,
            title: payload.title as string | undefined,
          });
        }
        if (!plan) throw new Error('performance.preload needs plan or set_url');
        await this.runtime.preload({
          avatarUrl: avatarUrl === 'basic' || avatarUrl.startsWith('basic:') ? avatarUrl : this.url(avatarUrl),
          audioUrl: this.url(audioUrl),
          plan,
          wordTimings: (payload.word_timings as never[]) ?? [],
          walkoutUrl: payload.walkout_url as string | undefined,
          name: payload.character_name as string | undefined,
          seed: payload.performance_id as string | undefined,
        });
        const pid = payload.performance_id as string | undefined;
        if (!pid || !this.readySeen.has(pid)) {
          this.consumer.sendStageAck({
            event: 'performance.ready',
            performance_id: pid,
            episode_id: payload.episode_id,
            avatar: this.runtime.telemetry().avatar,
          });
        }
        break;
      }
      case 'performance.start': {
        const created = Date.parse(event.created_at ?? '');
        const now = (this.opts.now ?? Date.now)();
        const lag = isFinite(created) ? now - created : 0;
        const dur = this.runtime.currentPlan?.duration_ms ?? 0;
        if (lag > (this.opts.catchUpAfterMs ?? 4000) && dur) {
          // Late join: approximate catch-up (ignores pauses taken meanwhile).
          if (lag < dur) this.runtime.playFrom(lag);
        } else {
          this.runtime.play();
        }
        break;
      }
      case 'performance.pause':
      case 'show.pause':
        this.runtime.pause();
        break;
      case 'performance.resume':
      case 'show.resume':
        this.runtime.resume();
        break;
      case 'performance.end':
      case 'show.end':
        this.runtime.end();
        this.stopMusic();
        break;
      case 'camera.cut':
        // Single source of truth: the shared contract (defense in depth;
        // the room already dropped unknown names).
        if (typeof payload.camera === 'string' && (CAMERA_NAMES as readonly string[]).includes(payload.camera)) {
          this.runtime.cutCamera(payload.camera as CameraPresetV1, 'human_director');
        }
        break;
      case 'crowd.reaction':
        if (typeof payload.reaction === 'string') this.runtime.react(payload.reaction);
        break;
      case 'audio.music.play':
        if (typeof payload.url === 'string') await this.playMusic(this.url(payload.url));
        break;
      case 'audio.music.stop':
        this.stopMusic();
        break;
      case 'audio.sfx.play': {
        const name = payload.name as string | undefined;
        const url = typeof payload.url === 'string' ? payload.url : (name ? this.opts.sfxUrl?.(name) ?? null : null);
        if (url) await this.runtime.audio.playUrl('SFX', this.url(url));
        else if (name) this.runtime.playSfx(name);
        break;
      }
      case 'face.expression': {
        const e = (payload.action ?? payload.emotion) as string | undefined;
        if (typeof e === 'string' && !payload.seat) this.runtime.faceExpression(e, Number(payload.intensity ?? 0.9), Number(payload.duration_ms ?? 2000));
        break;
      }
      case 'face.blendshapes':
        if (payload.weights && typeof payload.weights === 'object' && !payload.seat) this.runtime.faceBlendshapes(payload.weights as Record<string, number>);
        break;
      case 'face.affect':
        if (!payload.seat) this.runtime.faceAffect(Number(payload.a ?? 0), Number(payload.v ?? 0), Number(payload.p ?? 0), Number(payload.hold_ms ?? 4000));
        break;
      case 'character.enter':
        await this.runtime.lookAtAudience().catch(() => {});
        break;
      case 'character.exit':
        this.runtime.end();
        break;
      default:
        break;
    }
  }

  private async playMusic(url: string): Promise<void> {
    this.stopMusic();
    this.musicSource = await this.runtime.audio.playUrl('MUSIC', url);
    this.runtime.duckMusic();
  }

  private stopMusic(): void {
    if (this.musicSource) {
      try { this.musicSource.stop(); } catch { /* already stopped */ }
      this.musicSource = null;
    }
    this.runtime.unduckMusic();
  }
}
