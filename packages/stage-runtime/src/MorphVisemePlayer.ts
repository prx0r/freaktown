/**
 * MorphVisemePlayer — GLB-direct mouth driver (TalkingHead-style).
 *
 * For avatars that carry Oculus visemes (`viseme_aa` …) or ARKit mouth
 * shapes as GLB morph targets but are NOT VRM (the whole 39-cast is
 * GLB-first). Plays a viseme timeline — the speakAudio shape the take
 * pipeline emits (see scripts/build_visemes.py) — with smoothing.
 *
 * Channel discipline: mouth ONLY. Never touches emotion presets or
 * blink. Resolution never invents morph names: only targets present in
 * the file are bound (same honesty rule as face_profiles.py); intents
 * with no morph fall back to jaw/mouthOpen when present, else no-op.
 */

export interface VisemeDoc {
  visemes: string[];
  vtimes: number[];
  vdurations: number[];
}

interface Binding {
  setWeight(v: number): void;
  getWeight(): number;
}

// Oculus viseme -> morph names to accept, first present wins.
// ARKit/VRM0/MMD variants included (live-stage GlbAvatar list);
// jawOpen stays last (coarsest fallback, never preferred).
const VISEME_MORPHS: Record<string, string[]> = {
  sil: ['viseme_sil'],
  PP: ['viseme_PP'],
  FF: ['viseme_FF'],
  TH: ['viseme_TH'],
  DD: ['viseme_DD'],
  kk: ['viseme_kk'],
  CH: ['viseme_CH'],
  SS: ['viseme_SS'],
  nn: ['viseme_nn'],
  RR: ['viseme_RR'],
  aa: ['viseme_aa', 'mouthOpen', 'v_aa', 'aa', 'A', 'mouth_a', 'Fcl_MTH_A', 'jawOpen'],
  E: ['viseme_E', 'mouthStretchLeft', 'mouthStretchRight', 'v_e', 'ee', 'E', 'mouth_e', 'Fcl_MTH_E'],
  I: ['viseme_I', 'v_ih', 'ih', 'I', 'mouth_i', 'Fcl_MTH_I'],
  O: ['viseme_O', 'mouthFunnel', 'mouthPucker', 'v_oh', 'oh', 'O', 'mouth_o', 'Fcl_MTH_O'],
  U: ['viseme_U', 'mouthPucker', 'mouthFunnel', 'v_ou', 'ou', 'U', 'mouth_u', 'Fcl_MTH_U'],
};

/** Minimal morph-target mesh surface (three Mesh, or a fake in tests). */
export interface MorphMesh {
  morphTargetDictionary?: Record<string, number>;
  morphTargetInfluences?: number[];
}

// Every ARKit morph the emotion layer may address (ACTION_MORPHS in
// ExpressionLayer). Bound by exact name only; absent = ignored.
const EMOTION_MORPHS = [
  'mouthSmileLeft', 'mouthSmileRight',
  'mouthFrownLeft', 'mouthFrownRight',
  'browDownLeft', 'browDownRight', 'browInnerUp',
  'browOuterUpLeft', 'browOuterUpRight',
  'eyeSquintLeft', 'eyeSquintRight',
  'eyeWideLeft', 'eyeWideRight',
  'cheekSquintLeft', 'cheekSquintRight',
  'noseSneerLeft', 'noseSneerRight',
  'mouthFunnel', 'mouthPucker', 'jawOpen',
  'mouthStretchLeft', 'mouthStretchRight',
  'mouthPressLeft', 'mouthPressRight',
  'mouthLowerDownLeft', 'mouthLowerDownRight',
  'eyeBlinkLeft', 'eyeBlinkRight',
];

export class MorphVisemePlayer {
  private bindings = new Map<string, Binding[]>();
  /** Emotion morphs bound directly by ARKit name (face channel). */
  private emotionBindings = new Map<string, Binding[]>();
  private frames: { time: number; end: number; viseme: string }[] = [];
  private current = new Map<string, number>();
  hasMouth = false;

  /**
   * Scan an Object3D subtree for morph-target meshes and bind every
   * viseme intent that resolves to a real morph. Returns bound intents.
   */
  attachToObject(root: { traverse(cb: (o: unknown) => void): void }): string[] {
    this.bindings.clear();
    this.emotionBindings.clear();
    this.current.clear();
    const bound = new Set<string>();
    root.traverse((o: unknown) => {
      const mesh = o as MorphMesh;
      const dict = mesh.morphTargetDictionary;
      const infl = mesh.morphTargetInfluences;
      if (!dict || !infl) return;
      for (const [viseme, names] of Object.entries(VISEME_MORPHS)) {
        for (const name of names) {
          const idx = dict[name];
          if (typeof idx === 'number' && idx >= 0 && idx < infl.length) {
            const list = this.bindings.get(viseme) ?? [];
            list.push({
              setWeight: (v: number) => { infl[idx] = v; },
              getWeight: () => infl[idx] ?? 0,
            });
            this.bindings.set(viseme, list);
            bound.add(viseme);
          }
        }
      }
      // Emotion morphs: same honesty rule, bound by exact ARKit name.
      for (const name of EMOTION_MORPHS) {
        const idx = dict[name];
        if (typeof idx === 'number' && idx >= 0 && idx < infl.length) {
          const list = this.emotionBindings.get(name) ?? [];
          list.push({
            setWeight: (v: number) => { infl[idx] = v; },
            getWeight: () => infl[idx] ?? 0,
          });
          this.emotionBindings.set(name, list);
        }
      }
    });
    for (const v of bound) this.current.set(v, 0);
    this.hasMouth = bound.size > 0;
    return [...bound];
  }

  /** Emotion writer over the same bound morphs (mouth channel stays
   *  with playDoc/update; this is the face channel for GLB-direct).
   *  Unknown names are ignored, never invented. */
  writer(): { setValue(name: string, value: number): void } {
    return {
      setValue: (name: string, value: number) => {
        const list = this.emotionBindings.get(name);
        if (!list) return;
        for (const b of list) {
          try {
            b.setWeight(value);
          } catch {
            /* mesh gone */
          }
        }
      },
    };
  }

  /** Load a speakAudio-shape viseme doc. Unknown/empty -> no frames. */
  playDoc(doc: VisemeDoc | null | undefined): void {
    this.frames = [];
    try {
      const n = Math.min(
        doc?.visemes?.length ?? 0,
        doc?.vtimes?.length ?? 0,
        doc?.vdurations?.length ?? 0,
      );
      for (let i = 0; i < n; i++) {
        const viseme = String(doc!.visemes[i]);
        if (!this.bindings.has(viseme)) continue; // no morph, no frame
        const time = Number(doc!.vtimes[i]) || 0;
        const dur = Math.max(20, Number(doc!.vdurations[i]) || 0);
        this.frames.push({ time, end: time + dur, viseme });
      }
      this.frames.sort((a, b) => a.time - b.time);
    } catch {
      this.frames = [];
    }
  }

  /** Advance playback. Call per frame with the transport clock. */
  update(clockMs: number): void {
    if (!this.hasMouth || this.frames.length === 0) return;
    let active: string | null = null;
    for (const f of this.frames) {
      if (clockMs >= f.time && clockMs < f.end) active = f.viseme;
      else if (f.time > clockMs) break;
    }
    for (const [viseme, list] of this.bindings) {
      const isActive = viseme === active;
      // TalkingHead weights: PP/FF near-full close, others softer.
      const goal = !isActive ? 0 : viseme === 'PP' || viseme === 'FF' ? 0.9 : 0.6;
      const cur = this.current.get(viseme) ?? 0;
      const next = cur + (goal - cur) * 0.45;
      const settled = Math.abs(next - goal) < 0.01 ? goal : next;
      this.current.set(viseme, settled);
      for (const b of list) {
        try {
          b.setWeight(settled);
        } catch {
          /* mesh gone */
        }
      }
    }
  }
}
