/**
 * Transport — single clock for the entire show.
 *
 * Everything reads from this one clock:
 * - voice
 * - walkout
 * - motion
 * - captions
 * - camera
 * - timer
 * - reaction timestamps
 *
 * Do NOT use THREE.Clock as the show clock.
 * It should only calculate animation-frame delta.
 */

export type TransportState = 'idle' | 'playing' | 'paused' | 'ended';

export class Transport {
  private audioContext: AudioContext | null = null;
  private audioBuffer: AudioBuffer | null = null;
  private audioSource: AudioBufferSourceNode | null = null;
  private analyser: AnalyserNode | null = null;

  private startedContextTime: number = 0;
  private pausedMediaTime: number = 0;
  private offsetMs: number = 0;
  private _state: TransportState = 'idle';

  private onTimeUpdate?: (ms: number) => void;
  private onEnd?: () => void;
  private animationFrameId: number | null = null;

  get state(): TransportState {
    return this._state;
  }

  get currentTimeMs(): number {
    if (this._state === 'idle') return 0;
    if (this._state === 'paused') return this.pausedMediaTime;
    if (!this.audioContext) return 0;
    return (this.audioContext.currentTime - this.startedContextTime) * 1000 + this.offsetMs;
  }

  get durationMs(): number {
    return this.audioBuffer ? this.audioBuffer.duration * 1000 : 0;
  }

  get progress(): number {
    const d = this.durationMs;
    return d > 0 ? this.currentTimeMs / d : 0;
  }

  // ── Setup ────────────────────────────────────────────────────────

  setAudioContext(ctx: AudioContext): void {
    this.audioContext = ctx;
  }

  async loadAudio(url: string): Promise<void> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }

    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();
    this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

    // Set up analyser
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
  }

  async loadAudioFromBytes(bytes: ArrayBuffer): Promise<void> {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }

    this.audioBuffer = await this.audioContext.decodeAudioData(bytes);

    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
  }

  getAnalyser(): AnalyserNode | null {
    return this.analyser;
  }

  // ── Controls ─────────────────────────────────────────────────────

  play(): void {
    if (!this.audioBuffer || !this.audioContext) return;
    if (this._state === 'playing') return;

    // Resume audio context if suspended
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }

    // Create and connect audio source
    this.audioSource = this.audioContext.createBufferSource();
    this.audioSource.buffer = this.audioBuffer;

    if (this.analyser) {
      this.audioSource.connect(this.analyser);
      this.analyser.connect(this.audioContext.destination);
    } else {
      this.audioSource.connect(this.audioContext.destination);
    }

    // Start at the correct offset
    const startOffset = this._state === 'paused' ? this.pausedMediaTime / 1000 : 0;
    this.startedContextTime = this.audioContext.currentTime - startOffset;
    this.offsetMs = 0;

    this.audioSource.start(0, startOffset);
    this._state = 'playing';

    // Handle end
    this.audioSource.onended = () => {
      if (this._state === 'playing') {
        this._state = 'ended';
        this.onEnd?.();
      }
    };

    // Start time update loop
    this.startTimeLoop();
  }

  pause(): void {
    if (this._state !== 'playing') return;

    this.pausedMediaTime = this.currentTimeMs;
    if (this.audioSource) {
      try { this.audioSource.stop(); } catch {}
    }
    this._state = 'paused';
    this.stopTimeLoop();
  }

  resume(): void {
    if (this._state !== 'paused') return;
    this.play();
  }

  seek(ms: number): void {
    const wasPlaying = this._state === 'playing';

    if (wasPlaying && this.audioSource) {
      try { this.audioSource.stop(); } catch {}
    }

    this.pausedMediaTime = ms;
    this._state = 'paused';

    if (wasPlaying) {
      this.play();
    }
  }

  stop(): void {
    if (this.audioSource) {
      try { this.audioSource.stop(); } catch {}
    }
    this._state = 'idle';
    this.pausedMediaTime = 0;
    this.offsetMs = 0;
    this.stopTimeLoop();
  }

  // ── Time Loop ────────────────────────────────────────────────────

  private startTimeLoop(): void {
    const tick = () => {
      if (this._state !== 'playing') return;
      this.onTimeUpdate?.(this.currentTimeMs);
      this.animationFrameId = requestAnimationFrame(tick);
    };
    this.animationFrameId = requestAnimationFrame(tick);
  }

  private stopTimeLoop(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  // ── Callbacks ────────────────────────────────────────────────────

  setOnTimeUpdate(cb: (ms: number) => void): void {
    this.onTimeUpdate = cb;
  }

  setOnEnd(cb: () => void): void {
    this.onEnd = cb;
  }

  // ── Cleanup ──────────────────────────────────────────────────────

  dispose(): void {
    this.stop();
    if (this.audioSource) {
      try { this.audioSource.disconnect(); } catch {}
    }
    if (this.analyser) {
      try { this.analyser.disconnect(); } catch {}
    }
  }
}
