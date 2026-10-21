/**
 * compileHarnessBeats — Mutuals "mutuals-beats/v1" acting beats → MotionCue/CameraCue,
 * aligned to MEASURED word timings. Port of compile_harness_beats (harness_adapter.py,
 * feature/mutuals-acting-party-smiles 008d4f5). Fails closed: text/word mismatch,
 * unsorted timings or out-of-order spans throw — never estimate an acted punchline.
 */
import type { CameraCue, MotionCue, WordTiming } from '@freaktown/contracts';
import { HARNESS_CAMERAS, HARNESS_EMOTIONS, HARNESS_GESTURES } from './vocab';

export interface HarnessBeat { span: string; emotion?: string; register?: string; gesture?: string; camera?: string }
export interface HarnessCaps { humanoid?: boolean; expressions?: string[] }
export interface CompiledActing {
  motion: MotionCue[]; camera: CameraCue[]; warnings: string[];
  timing: 'provided-word-offsets'; source: 'mutuals-beats/v1';
}

const MAX_BEATS = 64;
const key = (x: string) => x.replace(/[^\p{L}\p{N}_]+/gu, '').toLowerCase();
const VRM_TARGET: Record<string, string> = {
  'face.smile': 'happy', 'face.smug': 'happy', 'face.frown': 'sad', 'face.annoyed': 'angry',
  'face.surprised': 'surprised', 'reaction.confused': 'surprised', 'face.deadpan': 'neutral', 'face.disgusted': 'angry',
};
const motion = (at: number, action: string, layer: 'upper' | 'face', duration = 900): MotionCue => ({
  at_ms: at, action, motion_asset_id: null, duration_ms: duration, intensity: 0.75,
  bone_mask: layer === 'upper' ? 'upper' : 'head', layer,
});

export function compileHarnessBeats(text: string, beats: HarnessBeat[], words: Array<Pick<WordTiming, 'word' | 'start_ms' | 'end_ms'>>, caps: HarnessCaps = {}): CompiledActing {
  if (typeof text !== 'string' || !text.trim()) throw new Error('text must be nonempty');
  if (!Array.isArray(beats) || beats.length > MAX_BEATS) throw new Error('too many beats or invalid beats');
  if (!Array.isArray(words) || words.length > 1024) throw new Error('words must be a bounded list of measured timings');
  const tokens = [...text.matchAll(/\S+/g)];
  if (tokens.length !== words.length) throw new Error('text/word alignment mismatch');
  tokens.forEach((t, i) => {
    const w = words[i];
    if (!w || key(t[0]) !== key(String(w.word ?? ''))) throw new Error(`text/word alignment mismatch at word ${i}`);
    if (typeof w.start_ms !== 'number' || typeof w.end_ms !== 'number' || w.end_ms < w.start_ms || w.start_ms < 0) throw new Error(`invalid word timing ${i}`);
    if (i && w.start_ms < words[i - 1].start_ms) throw new Error('word timings must be sorted');
  });
  const humanoid = caps.humanoid !== false;
  const supported = caps.expressions;
  const out: CompiledActing = { motion: [], camera: [], warnings: [], timing: 'provided-word-offsets', source: 'mutuals-beats/v1' };
  let cursor = 0, prev = -1;
  beats.forEach((beat, i) => {
    if (!beat || typeof beat.span !== 'string') throw new Error(`beat ${i} missing exact span`);
    const pos = beat.span ? text.indexOf(beat.span, cursor) : cursor;
    if (pos < 0 || pos >= text.length) throw new Error(`beat ${i} span missing or out of order`);
    let idx = tokens.findIndex((m) => m.index! <= pos && pos < m.index! + m[0].length);
    if (idx < 0) idx = tokens.findIndex((m) => m.index! > pos);
    if (idx < 0) throw new Error(`beat ${i} has no word to align`);
    const at = Math.round(words[idx].start_ms);
    if (at < prev) throw new Error('beats must be chronologically ordered');
    prev = at;
    cursor = pos + beat.span.length;
    const emotion = String(beat.emotion ?? '').toLowerCase();
    const gesture = String(beat.gesture ?? 'none').toLowerCase();
    const shot = String(beat.camera ?? 'none').toLowerCase();
    if (emotion && emotion !== 'none') {
      const action = HARNESS_EMOTIONS[emotion];
      if (action) {
        const target = VRM_TARGET[action];
        if (!Array.isArray(supported) || supported.includes(target) || target === 'neutral') out.motion.push(motion(at, action, 'face', 1500));
        else out.warnings.push(`unsupported expression: ${emotion}`);
      } else out.warnings.push(`unknown emotion: ${emotion}`);
    }
    if (gesture !== 'none') {
      if (HARNESS_GESTURES[gesture] && humanoid) out.motion.push(motion(at, HARNESS_GESTURES[gesture], 'upper'));
      else out.warnings.push(`unsupported gesture: ${gesture}`);
    }
    if (!['none', 'hold', ''].includes(shot)) {
      const cam = HARNESS_CAMERAS[shot];
      if (cam) out.camera.push({ at_ms: at, camera: cam });
      else out.warnings.push(`unknown camera: ${shot}`);
    }
  });
  out.motion.sort((a, b) => a.at_ms - b.at_ms);
  out.camera.sort((a, b) => a.at_ms - b.at_ms);
  return out;
}
