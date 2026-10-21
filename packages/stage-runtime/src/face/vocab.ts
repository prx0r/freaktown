/**
 * Acting vocabulary (Mutuals character-harness "mutuals-beats/v1" → FUNNIER cues).
 * From harness_adapter.py on feature/mutuals-acting-party-smiles (008d4f5;
 * inspiration github.com/mutuals-inc/character-harness, Apache-2.0) plus the
 * face_* aliases added to StageRuntime on that branch.
 */
import type { CameraPresetV1 } from '@funnier/contracts';

export const HARNESS_EMOTIONS: Record<string, string> = {
  happy: 'face.smile', playful: 'face.smile', warm: 'face.smile', amused: 'face.smile', smug: 'face.smug',
  excited: 'face.smile', sad: 'face.frown', shy: 'face.frown', grumpy: 'face.annoyed', angry: 'face.annoyed',
  annoyed: 'face.annoyed', surprised: 'face.surprised', shocked: 'face.surprised', confused: 'reaction.confused',
  deadpan: 'face.deadpan', neutral: 'face.deadpan', disgust: 'face.disgusted',
};
export const HARNESS_GESTURES: Record<string, string> = {
  wave: 'gesture.wave', nod: 'gesture.nod', shrug: 'gesture.shrug', point: 'gesture.point', cheer: 'gesture.cheer',
  lean: 'gesture.lean', 'lean-in': 'gesture.lean', sheepish: 'gesture.sheepish', surprise: 'gesture.surprise',
};
export const HARNESS_CAMERAS: Record<string, CameraPresetV1> = {
  'push-in': 'COMIC_CLOSE', 'close-up': 'COMIC_CLOSE', 'pull-back': 'WIDE_STAGE', wide: 'WIDE_STAGE',
  medium: 'COMIC_MEDIUM', side: 'SIDE_STAGE',
};
/** Set-camera equivalents of the harness shots (multi-seat sets). */
export const HARNESS_SET_CAMERAS: Record<string, (seat: string) => string> = {
  'push-in': (s) => `close:${s}`, 'close-up': (s) => `close:${s}`, 'pull-back': () => 'wide', wide: () => 'wide',
  medium: (s) => `single:${s}`, side: (s) => `reaction:${s}`,
};

/** Aliases seen in the wild → canonical face/gesture actions. */
export const FACE_ALIASES: Record<string, string> = {
  face_deadpan: 'face.deadpan', face_neutral: 'face.deadpan', face_whisper: 'face.deadpan',
  face_excited: 'face.smile', face_shout: 'face.annoyed', 'reaction.smile': 'face.smile',
  'face.happy': 'face.smile', 'face.sad': 'face.frown', 'face.angry': 'face.annoyed', 'face.neutral': 'face.deadpan',
  'face.shocked': 'face.surprised', 'face.confused': 'reaction.confused',
  shrug: 'gesture.shrug', point: 'gesture.point', wave: 'gesture.wave', lean_in: 'gesture.lean',
  'gesture.lean_in': 'gesture.lean', 'gesture.nod': 'gesture.nod',
};

/** Canonical action for a cue (aliases, bare harness emotions like "smug"). */
export function normalizeFaceAction(action: string): string {
  if (FACE_ALIASES[action]) return FACE_ALIASES[action];
  if (!action.includes('.') && !action.includes('_')) {
    if (HARNESS_EMOTIONS[action]) return HARNESS_EMOTIONS[action];
    if (HARNESS_GESTURES[action]) return HARNESS_GESTURES[action];
  }
  return action;
}

/** "smug" | "face.smug" | "face_excited" → face action, or null when unknown. */
export function emotionToFaceAction(emotion: string): string | null {
  const e = emotion.trim().toLowerCase();
  if (!e || e === 'none') return null;
  const n = normalizeFaceAction(e);
  return n.startsWith('face.') || n.startsWith('reaction.') ? n : null;
}
