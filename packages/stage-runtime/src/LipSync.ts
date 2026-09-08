/**
 * LipSyncAdapter — universal mouth driver for any audio source + avatar combo.
 *
 * Accepts any WebAudio AnalyserNode or MediaStream. Detects avatar
 * capabilities on load. Falls back gracefully:
 *
 *   VRM visemes (aa/ih/ou/ee/oh)  → full mouth
 *   VRM jaw only (jawOpen)         → simple open/close
 *   No mouth controls              → body-only (no mouth anim)
 *
 * Every mouth listens to its own audible voice. The source doesn't matter:
 *   - pre-recorded set.wav
 *   - Edge TTS streaming
 *   - OpenAI Realtime audio
 *   - LiveKit WebRTC track
 *   - Telnyx PCM
 *   - human microphone
 *
 * Invariant: this adapter writes ONLY mouth visemes. Emotion expressions
 * (happy/angry/etc.) belong to semantic beats. Blink belongs to its own
 * timer. They must never clear each other.
 */

import { VRM, VRMExpressionPresetName } from '@pixiv/three-vrm';

// ── Capability Detection ───────────────────────────────────────────

export type LipSyncMode = 'viseme' | 'jaw' | 'none';

export interface AvatarMouthCapabilities {
  mode: LipSyncMode;
  visemes: string[];    // available viseme names (aa, ih, ou, ee, oh)
  hasJawOpen: boolean;
  hasBlink: boolean;
}

/**
 * Detect what mouth controls a VRM actually has.
 * Call after GLTFLoader resolves the VRM.
 */
export function detectMouthCapabilities(vrm: VRM): AvatarMouthCapabilities {
  const em = vrm.expressionManager;
  if (!em) return { mode: 'none', visemes: [], hasJawOpen: false, hasBlink: false };

  // Check for standard VRM visemes
  const VRM_VISEMES: VRMExpressionPresetName[] = ['aa', 'ih', 'ou', 'ee', 'oh'];
  const present = VRM_VISEMES.filter((name) => {
    try {
      // If we can get/set it without error, it exists
      em.getValue(name);
      return true;
    } catch {
      return false;
    }
  });

  // Check for jawOpen (non-standard but common)
  let hasJawOpen = false;
  try {
    em.getValue('jawOpen');
    hasJawOpen = true;
  } catch {
    // Not available
  }

  // Check for blink
  let hasBlink = false;
  try {
    em.getValue('blink');
    hasBlink = true;
  } catch {
    // Not available
  }

  let mode: LipSyncMode;
  if (present.length >= 2) {
    mode = 'viseme';
  } else if (hasJawOpen) {
    mode = 'jaw';
  } else {
    mode = 'none';
  }

  return { mode, visemes: present, hasJawOpen, hasBlink };
}

// ── Frequency Band Extraction ──────────────────────────────────────

interface FrequencyBands {
  /** Low frequency energy (0-1). Drives jaw open. */
  low: number;
  /** Mid frequency energy (0-1). Drives tongue/round. */
  mid: number;
  /** High frequency energy (0-1). Drives lip spread. */
  high: number;
  /** Overall energy (0-1). For gating. */
  energy: number;
}

function extractBands(dataArray: Uint8Array): FrequencyBands {
  const binCount = dataArray.length;

  // Split spectrum into three bands
  const lowEnd = Math.floor(binCount * 0.15);  // ~15% = bass
  const midEnd = Math.floor(binCount * 0.5);   // ~35% = mid
  // highEnd = rest = treble

  let lowSum = 0, midSum = 0, highSum = 0, totalSum = 0;

  for (let i = 0; i < binCount; i++) {
    const val = dataArray[i] / 255;
    totalSum += val;
    if (i < lowEnd) lowSum += val;
    else if (i < midEnd) midSum += val;
    else highSum += val;
  }

  const lowCount = lowEnd;
  const midCount = midEnd - lowEnd;
  const highCount = binCount - midEnd;

  return {
    low: lowCount > 0 ? lowSum / lowCount : 0,
    mid: midCount > 0 ? midSum / midCount : 0,
    high: highCount > 0 ? highSum / highCount : 0,
    energy: binCount > 0 ? totalSum / binCount : 0,
  };
}

// ── LipSyncAdapter ────────────────────────────────────────────────

export class LipSyncAdapter {
  private analyser: AnalyserNode | null = null;
  private dataArray: Uint8Array<ArrayBuffer> | null = null;
  private vrm: VRM | null = null;
  private caps: AvatarMouthCapabilities = { mode: 'none', visemes: [], hasJawOpen: false, hasBlink: false };

  // Smoothing state
  private prevAA = 0;
  private prevIH = 0;
  private prevOH = 0;

  // Gate: 1 while speaking, 0 on pause — mouth closes instead of freezing
  private active = true;

  // ── Setup ──────────────────────────────────────────────────────

  /**
   * Attach to an existing analyser (e.g. the AudioBus voice tap).
   * Preferred: one audio graph, analyser owned by the bus.
   */
  attach(analyser: AnalyserNode): void {
    this.analyser = analyser;
    this.dataArray = new Uint8Array(analyser.frequencyBinCount);
  }

  /**
   * Create a new analyser from a raw AudioContext + source node.
   * Use when no AudioBus exists (e.g. standalone rehearsal).
   */
  connect(audioContext: AudioContext, sourceNode: AudioNode): void {
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    this.analyser.smoothingTimeConstant = 0.55;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    sourceNode.connect(this.analyser);
  }

  /**
   * Connect to a MediaStream (e.g. microphone).
   * Creates a MediaStreamAudioSourceNode internally.
   */
  connectStream(audioContext: AudioContext, stream: MediaStream): void {
    const source = audioContext.createMediaStreamSource(stream);
    this.connect(audioContext, source);
  }

  /**
   * Set the VRM avatar and detect its mouth capabilities.
   * Call after GLTFLoader resolves the VRM.
   */
  setVRM(vrm: VRM): void {
    this.vrm = vrm;
    this.caps = detectMouthCapabilities(vrm);
    console.log('[LipSync] Avatar mouth mode:', this.caps.mode,
      '| visemes:', this.caps.visemes.join(','),
      '| jaw:', this.caps.hasJawOpen,
      '| blink:', this.caps.hasBlink);
  }

  setActive(active: boolean): void {
    this.active = active;
  }

  /** Current detected capabilities. */
  get capabilities(): AvatarMouthCapabilities {
    return this.caps;
  }

  // ── Per-Frame Update ───────────────────────────────────────────

  /**
   * Update lip sync every animation frame.
   * Reads frequency data from the analyser and maps to avatar mouth.
   */
  update(): void {
    if (!this.analyser || !this.dataArray || !this.vrm?.expressionManager) return;
    if (this.caps.mode === 'none') return;

    this.analyser.getByteFrequencyData(this.dataArray);
    const bands = extractBands(this.dataArray);
    const gate = this.active ? 1 : 0;
    const em = this.vrm.expressionManager;

    if (this.caps.mode === 'viseme') {
      this.updateViseme(em, bands, gate);
    } else if (this.caps.mode === 'jaw') {
      this.updateJaw(em, bands, gate);
    }

    // Blink — independent channel, never cleared by mouth
    if (this.caps.hasBlink && Math.random() < 0.01) {
      em.setValue('blink', 1);
      setTimeout(() => {
        try { em.setValue('blink', 0); } catch { /* avatar gone */ }
      }, 100);
    }
  }

  private updateViseme(
    em: VRM['expressionManager'],
    bands: FrequencyBands,
    gate: number,
  ): void {
    if (!em) return;
    const SMOOTH = 0.3;

    // aa (mouth open) — driven by low frequency (bass = jaw energy)
    const targetAA = Math.min(1, bands.low * 2.5) * gate;
    this.prevAA = this.prevAA + (targetAA - this.prevAA) * SMOOTH;
    em.setValue('aa', this.prevAA);

    // ih (narrow/spread) — driven by high frequency (treble = sibilants)
    const targetIH = Math.min(1, bands.high * 3.0) * gate;
    this.prevIH = this.prevIH + (targetIH - this.prevIH) * SMOOTH;
    em.setValue('ih', this.prevIH * 0.6);

    // oh (round) — driven by mid frequency (formants = vowels)
    const targetOH = Math.min(1, bands.mid * 2.0) * gate;
    this.prevOH = this.prevOH + (targetOH - this.prevOH) * SMOOTH;
    em.setValue('oh', this.prevOH * 0.5);

    // ee and ou — secondary visemes derived from ih/oh
    try {
      em.setValue('ee', this.prevIH * 0.3);
      em.setValue('ou', this.prevOH * 0.3);
    } catch {
      // Some VRMs don't have ee/ou
    }
  }

  private updateJaw(
    em: VRM['expressionManager'],
    bands: FrequencyBands,
    gate: number,
  ): void {
    if (!em) return;
    const SMOOTH = 0.35;
    const target = Math.min(1, bands.energy * 3.0) * gate;
    const current = this.prevAA + (target - this.prevAA) * SMOOTH;
    this.prevAA = current;
    try {
      em.setValue('jawOpen', current);
    } catch {
      // Fall back to aa if jawOpen isn't available
      em.setValue('aa', current);
    }
  }

  // ── Offline Viseme Generation ──────────────────────────────────

  /**
   * Generate offline viseme timeline from word timings.
   * Used for pre-rendered performances where we don't have audio.
   */
  static generateVisemeTimeline(
    wordTimings: { word: string; start_ms: number; end_ms: number }[]
  ): { time_ms: number; aa: number; ih: number; ou: number; ee: number; oh: number }[] {
    const frames: { time_ms: number; aa: number; ih: number; ou: number; ee: number; oh: number }[] = [];

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
