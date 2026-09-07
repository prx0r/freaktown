/**
 * Lip Sync Adapter — drives VRM visemes from audio analyser.
 *
 * Edge TTS gives us MP3 audio. We use Web Audio analyser to extract
 * frequency energy and map it to VRM mouth shapes (visemes).
 *
 * For production: use Eleven v3 or Inworld for proper viseme data.
 */

import { VRM } from '@pixiv/three-vrm';

export interface VisemeFrame {
  time_ms: number;
  aa: number;  // mouth open
  ih: number;  // mouth narrow
  ou: number;  // mouth round
  ee: number;  // mouth wide
  oh: number;  // mouth O
}

export class LipSyncAdapter {
  private analyser: AnalyserNode | null = null;
  private dataArray: Uint8Array<ArrayBuffer> | null = null;
  private vrm: VRM | null = null;

  // Smoothing
  private prevMouth = 0;

  setVRM(vrm: VRM): void {
    this.vrm = vrm;
  }

  connect(audioContext: AudioContext, sourceNode: AudioNode): void {
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    sourceNode.connect(this.analyser);
  }

  /**
   * Update lip sync every frame.
   * Call from the animation loop.
   */
  update(): void {
    if (!this.analyser || !this.dataArray || !this.vrm?.expressionManager) return;

    this.analyser.getByteFrequencyData(this.dataArray);

    const em = this.vrm.expressionManager;

    // Extract frequency bands for different visemes
    const low = this.getAverage(0, 10);    // bass = jaw open
    const mid = this.getAverage(10, 40);   // mid = tongue
    const high = this.getAverage(40, 80);  // high = lips

    // Map to VRM visemes with smoothing
    const targetAA = Math.min(1, low / 200);   // aa = open mouth
    const targetIH = Math.min(1, high / 180);  // ih = narrow mouth
    const targetOH = Math.min(1, mid / 220);   // oh = round mouth

    const smooth = 0.3; // smoothing factor

    const aa = this.smooth(this.prevMouth, targetAA, smooth);
    this.prevMouth = aa;

    em.setValue('aa', aa);
    em.setValue('ih', targetIH * 0.5);
    em.setValue('oh', targetOH * 0.4);

    // Blink occasionally
    if (Math.random() < 0.01) {
      em.setValue('blink', 1);
      setTimeout(() => em.setValue('blink', 0), 100);
    }
  }

  private getAverage(start: number, end: number): number {
    if (!this.dataArray) return 0;
    let sum = 0;
    for (let i = start; i < end && i < this.dataArray.length; i++) {
      sum += this.dataArray[i];
    }
    return sum / (end - start);
  }

  private smooth(prev: number, target: number, factor: number): number {
    return prev + (target - prev) * factor;
  }

  /**
   * Generate offline viseme timeline from word timings.
   * Used for pre-rendered performances.
   */
  static generateVisemeTimeline(
    wordTimings: { word: string; start_ms: number; end_ms: number }[]
  ): VisemeFrame[] {
    const frames: VisemeFrame[] = [];

    for (const wt of wordTimings) {
      const duration = wt.end_ms - wt.start_ms;
      const syllables = Math.max(1, Math.ceil(wt.word.length / 3));

      for (let s = 0; s < syllables; s++) {
        const t = wt.start_ms + (duration / syllables) * s;
        const peak = s === Math.floor(syllables / 2) ? 1 : 0.5;

        frames.push({
          time_ms: t,
          aa: peak * 0.7,
          ih: peak * 0.2,
          ou: peak * 0.1,
          ee: peak * 0.3,
          oh: peak * 0.15,
        });
      }
    }

    return frames;
  }
}
