/**
 * StageEventExecutor — the execution layer.
 *
 * EventConsumer receives show events; the Zustand store mirrors state;
 * THIS class makes the runtime actually do things:
 *
 *   performance.preload → runtime.preload() → stage.performance_ready ACK
 *   performance.start   → runtime.play()       (READY only — gated)
 *   performance.pause   → runtime.pause()
 *   performance.resume  → runtime.resume()
 *   camera.cut          → runtime.cutCamera()
 *   audio.music.play    → play music URL on MUSIC bus (duck voice)
 *   audio.music.stop    → stop music, unduck
 *   audio.sfx.play      → play SFX by name (catalog URL map)
 *   character.enter     → gaze to audience
 *   character.exit      → pause transport
 *
 * The ready ACK goes back over the stage's own authenticated socket
 * (stage.ack → DO persists performance.ready) — no admin creds needed
 * on the stage, and the ACK itself becomes part of the event log.
 */

import type { StageRuntime } from './StageRuntime';
import type { EventConsumer } from './EventConsumer';
import type { CameraPresetName } from './CameraDirector';
import type { ShowEvent } from '../store/showStore';

const CAMERA_PRESETS: ReadonlySet<string> = new Set([
  'WIDE_STAGE', 'COMIC_MEDIUM', 'COMIC_CLOSE',
  'SIDE_STAGE', 'PANEL_WIDE', 'ELLA_CLOSE',
]);

export interface ExecutorOptions {
  /** Resolve asset keys/URLs. SFX names map to URLs here. */
  sfxUrl?: (name: string) => string | null;
  onError?: (message: string) => void;
}

export class StageEventExecutor {
  private runtime: StageRuntime;
  private consumer: EventConsumer;
  private opts: ExecutorOptions;
  private unsubscribe: (() => void) | null = null;
  private musicSource: AudioBufferSourceNode | null = null;

  constructor(runtime: StageRuntime, consumer: EventConsumer, opts: ExecutorOptions = {}) {
    this.runtime = runtime;
    this.consumer = consumer;
    this.opts = opts;
  }

  attach(): void {
    this.unsubscribe = this.consumer.onEvent((event) => {
      void this.execute(event).catch((e: unknown) =>
        this.opts.onError?.(e instanceof Error ? e.message : String(e))
      );
    });
  }

  detach(): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  async execute(event: ShowEvent): Promise<void> {
    const payload = event.payload ?? {};
    switch (event.type) {
      case 'performance.preload': {
        const avatarUrl = payload.avatar_url as string;
        const audioUrl = payload.audio_url as string;
        if (!avatarUrl || !audioUrl) {
          throw new Error('performance.preload missing avatar_url/audio_url');
        }
        await this.runtime.preload({
          avatarUrl,
          audioUrl,
          plan: payload.plan,
          wordTimings: payload.word_timings ?? [],
          walkoutUrl: payload.walkout_url,
        });
        this.consumer.sendStageAck({
          event: 'performance.ready',
          performance_id: payload.performance_id,
          episode_id: payload.episode_id,
        });
        break;
      }
      case 'performance.start':
        this.runtime.play();
        break;
      case 'performance.pause':
        this.runtime.pause();
        break;
      case 'performance.resume':
        this.runtime.resume();
        break;
      case 'performance.end':
        this.runtime.pause();
        break;
      case 'camera.cut':
        if (typeof payload.camera === 'string' && CAMERA_PRESETS.has(payload.camera)) {
          this.runtime.cutCamera(payload.camera as CameraPresetName);
        }
        break;
      case 'audio.music.play':
        if (typeof payload.url === 'string') {
          await this.playMusic(payload.url);
        }
        break;
      case 'audio.music.stop':
        this.stopMusic();
        break;
      case 'audio.sfx.play': {
        const name = payload.name as string | undefined;
        const url = typeof payload.url === 'string'
          ? payload.url
          : (name ? this.opts.sfxUrl?.(name) ?? null : null);
        if (url) await this.playSfx(url);
        break;
      }
      case 'character.enter':
        await this.runtime.lookAtAudience().catch(() => {});
        break;
      case 'character.exit':
        this.runtime.pause();
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

  private async playSfx(url: string): Promise<void> {
    await this.runtime.audio.playUrl('SFX', url);
  }
}
