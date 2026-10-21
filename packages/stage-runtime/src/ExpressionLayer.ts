/**
 * ExpressionLayer — the face (emotion) channel.
 *
 * Channel discipline (mirrors LipSync.ts): mouth = voice analyser,
 * face = beats + reactions (this layer), blink = timer. This layer
 * writes ONLY emotion presets and never touches mouth visemes
 * (aa/ih/ou/ee/oh/jawOpen) or blink — channels never clear each other.
 *
 * Every change runs an attack/hold/decay envelope so faces ramp instead
 * of popping. Accepts both `face.` and `face_` spellings (the Python
 * cue bridge emits `face_whisper`-style actions for the five delivery
 * words; see backend/services/freaktown/cues.py). Unknown actions no-op.
 */

export interface EmotionTarget {
  /** VRM emotion preset name (happy/angry/sad/surprised/neutral). */
  preset: string;
  /** Peak weight 0-1. */
  weight: number;
}

// Delivery-beat words + runtime face verbs -> VRM emotion targets.
// Existing executeFace mappings preserved exactly; this table only adds
// the previously-dead delivery words (whisper/shout/excited/normal) and
// the take-performance words (grin/confused). Keep in sync with
// face_voice.py DELIVERY_TO_FACE.
const ACTION_TARGETS: Record<string, EmotionTarget> = {
  'face.smile': { preset: 'happy', weight: 1.0 },
  'face.happy': { preset: 'happy', weight: 1.0 },
  'face.love': { preset: 'happy', weight: 0.9 },
  'face.frown': { preset: 'sad', weight: 1.0 },
  'face.sad': { preset: 'sad', weight: 1.0 },
  'face.angry': { preset: 'angry', weight: 1.0 },
  'face.annoyed': { preset: 'angry', weight: 1.0 },
  'face.surprised': { preset: 'surprised', weight: 1.0 },
  'face.deadpan': { preset: 'neutral', weight: 1.0 },
  'face.smug': { preset: 'happy', weight: 1.0 },
  'face.disgusted': { preset: 'angry', weight: 1.0 },
  'face.smirk': { preset: 'happy', weight: 0.7 },
  'face.contempt': { preset: 'angry', weight: 0.6 },
  'face.afraid': { preset: 'surprised', weight: 0.8 },
  // Real take timelines use these performance words:
  'face.grin': { preset: 'happy', weight: 1.0 },
  'face.confused': { preset: 'surprised', weight: 0.5 },
  // Delivery words (cues.py emits face_ spelling; both accepted below)
  'face.excited': { preset: 'happy', weight: 0.9 },
  'face.whisper': { preset: 'neutral', weight: 0.35 },
  'face.shout': { preset: 'surprised', weight: 0.8 },
  'face.normal': { preset: 'neutral', weight: 0.6 },
  'reaction.confused': { preset: 'surprised', weight: 1.0 },
  'reaction.annoyed': { preset: 'angry', weight: 1.0 },
  'reaction.shock': { preset: 'surprised', weight: 1.0 },
  'reaction.dead_stare': { preset: 'neutral', weight: 1.0 },
};

const EMOTION_PRESETS = ['happy', 'angry', 'sad', 'surprised', 'neutral'];

// Full-face ARKit recipes for the GLB-direct path: (morph, weight) at
// peak, before the action intensity multiplier. Mirrors
// face_profiles.py expression_morphs(); unknown morphs are ignored by
// the morph writer (binds only what the file carries).
const ACTION_MORPHS: Record<string, Array<[string, number]>> = {
  'face.smile': [['mouthSmileLeft', 1], ['mouthSmileRight', 1]],
  'face.happy': [['mouthSmileLeft', 1], ['mouthSmileRight', 1], ['cheekSquintLeft', 0.6], ['cheekSquintRight', 0.6]],
  'face.love': [['mouthSmileLeft', 1], ['mouthSmileRight', 1], ['cheekSquintLeft', 0.4], ['cheekSquintRight', 0.4]],
  'face.frown': [['mouthFrownLeft', 0.8], ['mouthFrownRight', 0.8]],
  'face.sad': [['mouthFrownLeft', 0.8], ['mouthFrownRight', 0.8], ['browInnerUp', 0.9], ['browDownLeft', 0.5], ['browDownRight', 0.5]],
  'face.angry': [['browDownLeft', 1], ['browDownRight', 1], ['eyeWideLeft', 0.5], ['eyeWideRight', 0.5], ['eyeSquintLeft', 0.5], ['eyeSquintRight', 0.5], ['noseSneerLeft', 0.5], ['noseSneerRight', 0.5], ['mouthPressLeft', 0.7], ['mouthPressRight', 0.7]],
  'face.annoyed': [['mouthFrownLeft', 0.4], ['browDownLeft', 0.5]],
  'face.surprised': [['jawOpen', 0.8], ['browInnerUp', 0.5], ['browOuterUpLeft', 0.7], ['browOuterUpRight', 0.7], ['eyeWideLeft', 0.9], ['eyeWideRight', 0.9]],
  'face.deadpan': [],
  'face.smug': [['mouthSmileLeft', 0.7]],
  'face.disgusted': [['noseSneerLeft', 0.9], ['noseSneerRight', 0.9], ['eyeWideLeft', 0.4], ['eyeWideRight', 0.4], ['mouthLowerDownLeft', 0.7], ['mouthLowerDownRight', 0.7]],
  'face.afraid': [['eyeWideLeft', 1], ['eyeWideRight', 1], ['browInnerUp', 0.6], ['mouthStretchLeft', 0.6], ['mouthStretchRight', 0.6], ['jawOpen', 0.5]],
  'face.smirk': [['mouthSmileLeft', 0.7]],
  'face.contempt': [['mouthSmileLeft', 0.8], ['browDownLeft', 0.5], ['eyeSquintLeft', 0.3], ['cheekSquintLeft', 0.4]],
  'face.grin': [['mouthSmileLeft', 1], ['mouthSmileRight', 1], ['cheekSquintLeft', 0.7], ['cheekSquintRight', 0.7]],
  'face.confused': [['mouthFrownLeft', 0.4], ['mouthFrownRight', 0.4], ['browInnerUp', 0.4]],
  'face.excited': [['mouthSmileLeft', 0.9], ['mouthSmileRight', 0.9], ['eyeWideLeft', 0.4], ['eyeWideRight', 0.4]],
  'face.whisper': [],
  'face.shout': [['jawOpen', 0.7], ['eyeWideLeft', 0.5], ['eyeWideRight', 0.5]],
  'face.normal': [],
  'reaction.confused': [['mouthFrownLeft', 0.4], ['mouthFrownRight', 0.4], ['browInnerUp', 0.4]],
  'reaction.annoyed': [['mouthFrownLeft', 0.7], ['mouthFrownRight', 0.7], ['browDownLeft', 1], ['browDownRight', 1]],
  'reaction.shock': [['jawOpen', 0.8], ['eyeWideLeft', 0.9], ['eyeWideRight', 0.9]],
  'reaction.dead_stare': [],
};

/** Minimal expression-manager surface (VRM's, or a fake in tests). */
export interface EmotionWriter {
  setValue(name: string, value: number): void;
}

export interface ProsodyFrame {
  t_ms: number;
  accent: number; // 0-1 brow flash (AU1+AU2)
  arousal: number; // 0-1 eye widening (AU5)
  phrase_end: number; // 1 = blink + decay (AU45)
}

// Prosody -> morph offsets. Small and additive UNDER beat/reactor
// emotions (beats win ties by writing first each frame... in practice
// both converge; prosody weights are capped low so it can only lift).
const PROSODY_MORPHS: Array<[string, (p: ProsodyFrame) => number]> = [
  ['browInnerUp', (p) => 0.35 * p.accent],
  ['browOuterUpLeft', (p) => 0.3 * p.accent],
  ['browOuterUpRight', (p) => 0.3 * p.accent],
  ['eyeWideLeft', (p) => 0.25 * p.arousal],
  ['eyeWideRight', (p) => 0.25 * p.arousal],
];

export interface ExpressionOpts {
  attackMs?: number;
  holdMs?: number;
  decayMs?: number;
}

export class ExpressionLayer {
  private current = new Map<string, number>();
  private target: EmotionTarget = { preset: 'neutral', weight: 0 };
  private morphTargets: Array<[string, number]> = [];
  private morphCurrent = new Map<string, number>();
  /** Second writer for GLB-direct ARKit morphs (null on VRM path). */
  morphWriter: EmotionWriter | null = null;
  /** AU prosody track (aus.json). Advanced by the clock each update. */
  private prosodyFrames: ProsodyFrame[] = [];
  private prosodyIdx = 0;
  private prosody: ProsodyFrame = { t_ms: 0, accent: 0, arousal: 0, phrase_end: 0 };
  /** Blink pulse 0-1, set on phrase_end, decays over ~150 ms wall time. */
  private blinkPulse = 0;
  private lastTickMs = 0;
  private attackMs = 120;
  private holdMs = 2000;
  private decayMs = 300;
  private phase: 'idle' | 'attack' | 'hold' | 'decay' = 'idle';
  private phaseStart = 0;
  private nowMs = 0;

  constructor() {
    for (const p of EMOTION_PRESETS) this.current.set(p, 0);
  }

  /**
   * Queue an expression. Unknown actions no-op (never raise on stage).
   * Normalises `face_whisper` -> `face.whisper` before lookup.
   */
  setExpression(action: string, intensity = 1.0, opts: ExpressionOpts = {}): boolean {
    const key = action.replace(/^face_/, 'face.');
    const base = ACTION_TARGETS[key];
    if (!base) return false;
    const w = Math.max(0, Math.min(1, intensity));
    this.target = { preset: base.preset, weight: base.weight * w };
    this.morphTargets = (ACTION_MORPHS[key] ?? []).map(
      ([name, wt]) => [name, wt * w] as [string, number]);
    this.attackMs = opts.attackMs ?? 120;
    this.holdMs = opts.holdMs ?? 2000;
    this.decayMs = opts.decayMs ?? 300;
    this.phase = 'attack';
    this.phaseStart = this.nowMs;
    return true;
  }

  /** Load an AU prosody track (aus.json frames). Unknown/empty -> off. */
  playProsody(frames: ProsodyFrame[] | null | undefined): void {
    try {
      this.prosodyFrames = (frames ?? []).filter(
        (f) => f && typeof f.t_ms === 'number',
      );
      this.prosodyFrames.sort((a, b) => a.t_ms - b.t_ms);
    } catch {
      this.prosodyFrames = [];
    }
    this.prosodyIdx = 0;
    this.prosody = { t_ms: 0, accent: 0, arousal: 0, phrase_end: 0 };
  }

  private advanceProsody(nowMs: number): void {
    const fs = this.prosodyFrames;
    while (this.prosodyIdx < fs.length && fs[this.prosodyIdx].t_ms <= nowMs) {
      this.prosody = fs[this.prosodyIdx];
      this.prosodyIdx++;
      if (this.prosody.phrase_end) this.blinkPulse = 1;
    }
    // Wall-time decay: same 150 ms blink at any frame rate.
    const dt = Math.max(0, nowMs - this.lastTickMs);
    this.lastTickMs = nowMs;
    this.blinkPulse = Math.max(0, this.blinkPulse - dt / 150);
  }

  /** Advance the envelope and write smoothed weights. Call per frame. */
  update(nowMs: number, em: EmotionWriter | null | undefined): void {
    if (!em && !this.morphWriter) return;
    this.nowMs = nowMs;
    this.advancePhase();
    this.advanceProsody(nowMs);
    const rate = this.phase === 'attack'
      ? rateFor(this.attackMs)
      : rateFor(this.decayMs);
    const active = this.phase !== 'decay' && this.phase !== 'idle';
    if (em) {
      for (const p of EMOTION_PRESETS) {
        const goal = active && p === this.target.preset ? this.target.weight : 0;
        this.current.set(p, approach(this.current.get(p) ?? 0, goal, rate));
        try {
          em.setValue(p, this.current.get(p) ?? 0);
        } catch {
          /* avatar gone */
        }
      }
    }
    if (this.morphWriter) {
      // Beat/reactor targets first.
      const goals = new Map<string, number>();
      if (active) {
        for (const [name, wt] of this.morphTargets) goals.set(name, wt);
      }
      // Prosody offsets add UNDER beat emotions (capped; beats win ties).
      for (const [name, lift] of this.prosodyOffsets()) {
        goals.set(name, Math.min(1, (goals.get(name) ?? 0) + lift));
      }
      // Blink pulse on phrase end (AU45). Written directly, bypassing
      // the converge loop: the pulse itself is the envelope (150 ms
      // wall time), and lag would swallow it. Different morphs from
      // mouth and VRM blink, so no channel fights.
      if (this.blinkPulse > 0.01) {
        for (const b of ['eyeBlinkLeft', 'eyeBlinkRight']) {
          this.morphCurrent.set(b, this.blinkPulse);
          this.writeMorph(b, this.blinkPulse);
        }
      } else {
        for (const b of ['eyeBlinkLeft', 'eyeBlinkRight']) {
          if ((this.morphCurrent.get(b) ?? 0) > 0) {
            this.morphCurrent.delete(b);
            this.writeMorph(b, 0);
          }
        }
      }
      // Converge everything toward its goal; drop the settled.
      const live = new Set(goals.keys());
      for (const [name, goal] of goals) {
        const next = approach(this.morphCurrent.get(name) ?? 0, goal,
                              rate);
        this.morphCurrent.set(name, next);
        this.writeMorph(name, next);
      }
      for (const [name, cur] of this.morphCurrent) {
        if (live.has(name)) continue;
        const next = approach(cur, 0, rate);
        if (next < 0.005) {
          this.morphCurrent.delete(name);
          this.writeMorph(name, 0);
        } else {
          this.morphCurrent.set(name, next);
          this.writeMorph(name, next);
        }
      }
    }
  }

  private writeMorph(name: string, value: number): void {
    try {
      this.morphWriter!.setValue(name, value);
    } catch {
      /* mesh gone */
    }
  }

  /** Current prosody lifts as (morph, weight) pairs. */
  private prosodyOffsets(): Array<[string, number]> {
    const out: Array<[string, number]> = [];
    for (const [name, fn] of PROSODY_MORPHS) {
      try {
        const lift = fn(this.prosody);
        if (lift > 0.005) out.push([name, Math.min(0.4, lift)]);
      } catch {
        /* bad frame */
      }
    }
    return out;
  }

  private advancePhase(): void {
    const elapsed = this.nowMs - this.phaseStart;
    if (this.phase === 'attack' && elapsed >= this.attackMs) {
      this.phase = 'hold';
      this.phaseStart = this.nowMs;
    } else if (this.phase === 'hold' && elapsed >= this.holdMs) {
      this.phase = 'decay';
      this.phaseStart = this.nowMs;
    } else if (this.phase === 'decay' && elapsed >= this.decayMs) {
      this.phase = 'idle';
    }
  }
}

/** Per-update convergence fraction for a ~60fps tick and given ms. */
function rateFor(ms: number): number {
  if (ms <= 0) return 1;
  return Math.min(1, 48 / ms);
}

/** Exponential approach with snap-to-goal. */
function approach(cur: number, goal: number, rate: number): number {
  const next = cur + (goal - cur) * rate;
  return Math.abs(next - goal) < 0.005 ? goal : next;
}
