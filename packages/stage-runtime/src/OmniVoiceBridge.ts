/**
 * OmniVoiceBridge — Qwen Omni audio-out -> voice bus -> moving mouth.
 *
 * Omni's realtime stream returns base64 24 kHz mono PCM chunks
 * (`response.audio.delta`). This bridge assembles chunks into
 * AudioBuffers and plays them on the VOICE channel, so they flow through
 * the voice analyser and the existing LipSyncAdapter moves the mouth
 * with zero new lipsync code. Mouth stays on voice; the reactor brain
 * (see omni_reactor.py) only emits face/gaze/gesture — channels never
 * fight.
 *
 * Playback clock: chunks are queued in arrival order on the single
 * transport clock (no second clock). Backpressure: at most MAX_QUEUED
 * buffers wait; overflow drops oldest (live room beats completeness).
 */

import type { AudioBus } from './AudioBus';

const OMNI_RATE = 24000;
const MAX_QUEUED = 8;

export class OmniVoiceBridge {
  private pending: Float32Array[] = [];
  private playing = false;

  constructor(
    private audioContext: AudioContext,
    private audioBus: AudioBus,
  ) {}

  /** Push one decoded PCM chunk (mono float, 24 kHz). Never raises. */
  pushPcm(samples: Float32Array): void {
    try {
      if (!samples || samples.length === 0) return;
      this.pending.push(samples);
      if (this.pending.length > MAX_QUEUED) this.pending.shift();
      void this.drain();
    } catch {
      /* live room: drop, don't die */
    }
  }

  /** Push one base64 PCM16 chunk straight from the WS delta. */
  pushBase64Pcm16(b64: string): void {
    try {
      const bin = atob(b64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const view = new DataView(bytes.buffer);
      const out = new Float32Array(bytes.length / 2);
      for (let i = 0; i < out.length; i++) {
        out[i] = view.getInt16(i * 2, true) / 32768;
      }
      this.pushPcm(out);
    } catch {
      /* drop */
    }
  }

  queued(): number {
    return this.pending.length + (this.playing ? 1 : 0);
  }

  private async drain(): Promise<void> {
    if (this.playing) return;
    const next = this.pending.shift();
    if (!next) return;
    this.playing = true;
    try {
      const buf = this.audioContext.createBuffer(1, next.length, OMNI_RATE);
      buf.getChannelData(0).set(next);
      const src = this.audioBus.playBuffer('VOICE', buf);
      await new Promise<void>((resolve) => {
        src.onended = () => resolve();
        // Safety: never hang the queue on a lost event.
        setTimeout(resolve, (next.length / OMNI_RATE) * 1000 + 500);
      });
    } catch {
      /* drop */
    } finally {
      this.playing = false;
      if (this.pending.length > 0) void this.drain();
    }
  }
}
