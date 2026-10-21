/**
 * Set adapter — sealed set (scripts/build_set.py outputs) → PerformancePlan.
 *
 *   set.wav            composed audio (compositor-measured, FT-03 timing authority)
 *   timeline.json      [{beat_id,type,start_ms,end_ms,text,performance,…}]
 *   mouth_cues.json    [{start_ms,end_ms,shape:"open"}]  (envelope of set.wav)
 *   set_plan.json      {character_id, premise, delivery, …} (optional)
 *
 * Word timings: build_set writes beat spans, not words. Words are laid onto
 * the beat's VOICED time (the envelope spans inside the beat), weighted by
 * syllable estimate, so each word lands on real speech, not on a guess of
 * the TTS rate. Honest label: derived, not forced-aligned.
 *
 * Camera: WIDE open → MEDIUM on the set-up → SIDE on escalations →
 * CLOSE on the last sentence of each punchline (close-ups punchline-only,
 * per docs/P0-STUDIO.md) → WIDE for the laugh → MEDIUM closer → WIDE out.
 * Cues live inside the plan, so replaying the preload event reproduces
 * every cut (replay invariant).
 */

import { compileHarnessBeats } from '../face/harnessBeats';
import type {
  CameraCue, CameraPresetV1, MotionCue, MouthSpan, PerformancePlan, PlanBeat, WordTiming,
} from '@freaktown/contracts';
// One PhoneticViseme source of truth (MouthTrack); redefining it here made
// the package index export the same name twice (TS2308).
import type { PhoneticViseme } from '../performance/MouthTrack';
export type { PhoneticViseme };

export interface TimelineBeat {
  beat_id: string;
  type: string;
  start_ms: number;
  end_ms: number;
  dur_ms?: number;
  pause_before_ms?: number;
  pause_after_ms?: number;
  text: string;
  performance?: { expression?: string; gesture?: string; look?: string; [k: string]: unknown };
}

/** One real phonetic viseme (take visemes.json: TalkingHead-en) — type lives
 *  in performance/MouthTrack; imported above, re-exported for callers. */

/** AU prosody frame (take aus.json: au_track.py). */
export interface ProsodyFrameInput {
  t_ms: number;
  accent: number;
  arousal: number;
  phrase_end: number;
}

export interface SealedSetInput {
  timeline: TimelineBeat[];
  mouthCues?: MouthSpan[];
  /** Take visemes.json (optional): full-word phonetics, preferred over
   *  vowel-group guessing in MouthTrack. */
  visemes?: { visemes: string[]; vtimes: number[]; vdurations: number[] };
  /** Take aus.json (optional): AU prosody track for brows/eyes/blink. */
  aus?: { frames: ProsodyFrameInput[] };
  setPlan?: {
    character_id?: string;
    premise?: string;
    mesh?: string;
    delivery?: { profile?: { energy?: number; pace?: number }; beats?: Array<{ id: string; performance?: Record<string, unknown> }> };
    [k: string]: unknown;
  };
  /** Decoded audio duration; falls back to the last beat end + hold. */
  durationMs?: number;
  appearanceId?: string;
  title?: string;
  bodyClass?: string;
  /** MEASURED word timings (words.json: edge-TTS WordBoundary / forced alignment). Preferred over the envelope spread. */
  words?: Array<{ word: string; start_ms: number; end_ms: number }>;
  /** Mutuals acting overlay (mutuals-beats/v1). Applied only with measured `words`; fails closed (warnings). */
  acting?: { schema?: string; beats: Array<{ span: string; emotion?: string; gesture?: string; camera?: string; register?: string }> };
}

// ── words ──────────────────────────────────────────────────────────

export function splitWords(text: string): string[] {
  return text.split(/\s+/).map((w) => w.trim()).filter(Boolean);
}

/** Rough syllable count (vowel groups), ≥1. Punctuation adds a micro-pause weight. */
export function wordWeight(word: string): number {
  const clean = word.toLowerCase().replace(/[^a-z0-9]/g, '');
  const groups = clean.match(/[aeiouy]+/g)?.length ?? 0;
  const digits = clean.match(/[0-9]/g)?.length ?? 0;
  let w = Math.max(1, groups + digits);
  if (/[,;:]$/.test(word)) w += 0.6;
  if (/[.!?]$/.test(word)) w += 1.0;
  return w;
}

interface Span { start: number; end: number }

function voicedSpans(beat: TimelineBeat, mouth: MouthSpan[]): Span[] {
  const spans: Span[] = [];
  for (const m of mouth) {
    const s = Math.max(m.start_ms, beat.start_ms);
    const e = Math.min(m.end_ms, beat.end_ms);
    if (e - s >= 20) spans.push({ start: s, end: e });
  }
  if (!spans.length) spans.push({ start: beat.start_ms, end: beat.end_ms });
  return spans;
}

/** Map a fraction [0,1] of total voiced time to an absolute ms. */
function voicedAt(spans: Span[], total: number, frac: number): number {
  let target = Math.max(0, Math.min(1, frac)) * total;
  for (const sp of spans) {
    const len = sp.end - sp.start;
    if (target <= len) return sp.start + target;
    target -= len;
  }
  return spans[spans.length - 1].end;
}

export function deriveWordTimings(timeline: TimelineBeat[], mouth: MouthSpan[] = []): WordTiming[] {
  const out: WordTiming[] = [];
  let index = 0;
  for (const beat of timeline) {
    const words = splitWords(beat.text);
    if (!words.length) continue;
    const spans = voicedSpans(beat, mouth);
    const total = spans.reduce((a, s) => a + (s.end - s.start), 0);
    const weights = words.map(wordWeight);
    const wsum = weights.reduce((a, b) => a + b, 0);
    let acc = 0;
    words.forEach((word, i) => {
      const f0 = acc / wsum;
      acc += weights[i];
      const f1 = acc / wsum;
      const start = Math.round(voicedAt(spans, total, f0));
      const end = Math.max(start + 40, Math.round(voicedAt(spans, total, f1)));
      out.push({ word, start_ms: start, end_ms: Math.min(end, beat.end_ms), index: index++, beat_id: beat.beat_id });
    });
  }
  return out;
}

// ── cues ───────────────────────────────────────────────────────────

function cue(at_ms: number, action: string, intensity: number, duration_ms: number,
  layer: MotionCue['layer'], metadata?: Record<string, unknown>): MotionCue {
  return {
    at_ms: Math.max(0, Math.round(at_ms)), action, motion_asset_id: null,
    duration_ms: Math.round(duration_ms), intensity: Math.round(intensity * 100) / 100,
    bone_mask: layer === 'face' ? 'face' : layer === 'head' ? 'head' : layer === 'upper' ? 'upper_body' : 'full',
    layer, metadata,
  };
}

const EXPRESSION_ACTION: Record<string, string> = {
  deadpan: 'face.deadpan', smug: 'face.smug', smile: 'face.smile', annoyed: 'face.annoyed',
  surprised: 'face.surprised', frown: 'face.frown', disgusted: 'face.disgusted',
  // Extended beat vocabulary (delivery beats + reactor; GlbAvatar renders
  // the full FACS recipes, VRM falls back to the Performer presets):
  grin: 'face.grin', confused: 'face.confused', afraid: 'face.afraid',
  contempt: 'face.contempt', happy: 'face.happy', love: 'face.love',
  sad: 'face.sad', angry: 'face.angry', excited: 'face.excited',
  whisper: 'face.whisper', shout: 'face.shout', normal: 'face.normal',
};

/** Start of the last sentence of a beat (the actual punch), via word timings. */
function lastSentenceStart(beat: TimelineBeat, words: WordTiming[]): number {
  const ws = words.filter((w) => w.beat_id === beat.beat_id);
  if (ws.length < 2) return beat.start_ms;
  for (let i = ws.length - 2; i >= 0; i--) {
    if (/[.!?]$/.test(ws[i].word)) return ws[i + 1].start_ms;
  }
  return beat.start_ms;
}

export function adaptSealedSet(input: SealedSetInput): PerformancePlan {
  const timeline = [...input.timeline].sort((a, b) => a.start_ms - b.start_ms);
  const mouth = input.mouthCues ?? [];
  const measured = !!input.words?.length;
  const words: WordTiming[] = measured
    ? input.words!.map((w, index) => ({
      word: w.word, start_ms: Math.round(w.start_ms), end_ms: Math.round(w.end_ms), index,
      beat_id: (timeline.find((b) => w.start_ms >= b.start_ms - 50 && w.start_ms < b.end_ms + 50) ?? timeline[timeline.length - 1])?.beat_id,
    }))
    : deriveWordTimings(timeline, mouth);
  const lastBeat = timeline[timeline.length - 1];
  const duration = Math.round(input.durationMs
    ?? (lastBeat ? lastBeat.end_ms + (lastBeat.pause_after_ms ?? 0) : 0));
  const profile = input.setPlan?.delivery?.profile ?? {};
  const energy = typeof profile.energy === 'number' ? profile.energy : 0.7;
  const deliveryPerf = new Map<string, Record<string, unknown>>();
  for (const b of input.setPlan?.delivery?.beats ?? []) {
    if (b.performance) deliveryPerf.set(b.id, b.performance);
  }

  const cues: MotionCue[] = [];
  const cams: CameraCue[] = [{ at_ms: 0, camera: 'WIDE_STAGE', reason: 'open' }];
  const pushCam = (at: number, camera: CameraPresetV1, reason: string) => {
    const prev = cams[cams.length - 1];
    if (prev.camera === camera) return;
    if (at - prev.at_ms < 1200) { // never strobe: replace a too-recent cut
      if (cams.length > 1) { cams[cams.length - 1] = { at_ms: prev.at_ms, camera, reason }; return; }
      at = prev.at_ms + 1200;
    }
    cams.push({ at_ms: Math.round(at), camera, reason });
  };

  cues.push(cue(0, 'gaze.audience', 1, 1500, 'head'));
  let escalationN = 0;
  timeline.forEach((beat, bi) => {
    const len = Math.max(1, beat.end_ms - beat.start_ms);
    const perf = { ...(deliveryPerf.get(beat.beat_id) ?? {}), ...(beat.performance ?? {}) } as Record<string, string>;
    const hold = beat.pause_after_ms ?? 300;
    switch (beat.type) {
      case 'setup': {
        cues.push(cue(beat.start_ms + 200, 'face.smile', 0.35 * energy, 2000, 'face'));
        cues.push(cue(beat.start_ms + len * 0.3, 'gesture.open', 0.5 * energy, 1600, 'upper'));
        cues.push(cue(beat.start_ms + len * 0.75, 'gesture.point', 0.45, 1200, 'upper'));
        pushCam(beat.start_ms + Math.min(2500, len * 0.35), 'COMIC_MEDIUM', 'setup');
        break;
      }
      case 'escalation': {
        escalationN += 1;
        const k = Math.min(1, 0.45 + 0.15 * escalationN);
        cues.push(cue(beat.start_ms + 150, escalationN % 2 ? 'gaze.left' : 'gaze.right', 0.6, 1500, 'head'));
        cues.push(cue(beat.start_ms + len * 0.25, 'gesture.shrug', k * energy, 1400, 'upper'));
        cues.push(cue(beat.start_ms + len * 0.55, 'face.annoyed', 0.3 + 0.1 * escalationN, 2200, 'face'));
        cues.push(cue(beat.start_ms + len * 0.7, 'gesture.open', k, 1500, 'upper'));
        cues.push(cue(beat.start_ms + len * 0.6, 'gaze.audience', 1, 1200, 'head'));
        pushCam(beat.start_ms + 150, escalationN % 2 ? 'SIDE_STAGE' : 'COMIC_MEDIUM', `escalation ${escalationN}`);
        break;
      }
      case 'punchline': {
        const punch = lastSentenceStart(beat, words);
        cues.push(cue(beat.start_ms, 'gaze.audience', 1, 1000, 'head'));
        pushCam(beat.start_ms + 100, 'COMIC_MEDIUM', 'punchline setup');
        cues.push(cue(punch - 150, 'pose.lean_forward', 0.8, beat.end_ms - punch + 300, 'base'));
        cues.push(cue(punch, EXPRESSION_ACTION[perf.expression ?? 'deadpan'] ?? 'face.deadpan', 0.9, beat.end_ms - punch + hold, 'face'));
        if (perf.gesture === 'hold') cues.push(cue(beat.end_ms, 'locomotion.freeze', 1, hold, 'upper'));
        pushCam(punch - 120, 'COMIC_CLOSE', 'punchline');
        cues.push(cue(beat.end_ms + hold * 0.4, 'face.smug', 0.7, 1500, 'face'));
        cues.push(cue(beat.end_ms + hold * 0.4, 'pose.confident', 0.6, 1200, 'base'));
        const next = timeline[bi + 1];
        if (next) pushCam(Math.max(beat.end_ms + hold * 0.5, punch + 1300), 'WIDE_STAGE', 'laugh');
        break;
      }
      case 'closer': {
        cues.push(cue(beat.start_ms + 150, 'face.smile', 0.6, 2500, 'face'));
        cues.push(cue(beat.start_ms + len * 0.4, 'gesture.open', 0.6, 1500, 'upper'));
        cues.push(cue(beat.end_ms - 400, 'gesture.wave', 0.9, 1800, 'upper'));
        pushCam(beat.start_ms + 400, 'COMIC_MEDIUM', 'closer');
        pushCam(beat.end_ms, 'WIDE_STAGE', 'out');
        break;
      }
      default: {
        cues.push(cue(beat.start_ms + len * 0.4, 'gesture.open', 0.5, 1400, 'upper'));
        break;
      }
    }
  });

  const actingWarnings: string[] = [];
  if (input.acting?.beats?.length) {
    if (!measured) actingWarnings.push('acting ignored: needs measured words (words.json)');
    else {
      try {
        const text = timeline.map((b) => b.text).join(' ');
        const acted = compileHarnessBeats(text, input.acting.beats, words);
        cues.push(...acted.motion);
        for (const c of acted.camera) pushCam(c.at_ms, c.camera, 'acting');
        actingWarnings.push(...acted.warnings);
      } catch (e) {
        actingWarnings.push(`acting rejected: ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  }
  cams.sort((a, b) => a.at_ms - b.at_ms);

  cues.sort((a, b) => a.at_ms - b.at_ms);
  const beats: PlanBeat[] = timeline.map((b) => ({
    id: b.beat_id, type: b.type, start_ms: b.start_ms, end_ms: b.end_ms, text: b.text,
  }));
  const characterId = input.setPlan?.character_id;
  // Face tracks ride the plan as extra props (typed at the call site):
  // take visemes.json (TalkingHead-en phonetics) + aus.json (AU prosody).
  const faceTracks = {
    ...(input.visemes ? { visemes: input.visemes } : {}),
    ...(input.aus ? { aus: input.aus } : {}),
  };
  return {
    appearance_id: input.appearanceId ?? characterId ?? 'appearance',
    body_class: input.bodyClass ?? 'auto',
    duration_ms: duration,
    base_idle_asset_id: null,
    energy,
    stillness: Math.round((1 - energy) * 100) / 100,
    gesture_density: Math.round((cues.filter((c) => c.action.startsWith('gesture.')).length / Math.max(1, duration / 60000)) * 10) / 10,
    cue_count: cues.length,
    cues,
    title: input.title ?? input.setPlan?.premise,
    character_id: characterId,
    beats,
    word_timings: words,
    mouth,
    camera_cues: cams.filter((c) => c.at_ms <= duration),
    source: { adapter: 'sealed-set.v1', words: measured ? 'measured' : 'derived-from-envelope', ...(input.acting ? { acting: 'mutuals-beats/v1', acting_warnings: actingWarnings } : {}) },
    ...faceTracks,
  };
}

/** Fetch a build_set output directory over HTTP and adapt it. */
export async function loadSealedSet(baseUrl: string, opts: Partial<SealedSetInput> = {}): Promise<PerformancePlan> {
  const base = baseUrl.replace(/\/$/, '');
  const getJson = async <T>(name: string, optional: boolean): Promise<T | undefined> => {
    const res = await fetch(`${base}/${name}`);
    if (!res.ok) {
      if (optional) return undefined;
      throw new Error(`sealed set: ${name} ${res.status}`);
    }
    try { return (await res.json()) as T; } catch (e) { if (optional) return undefined; throw e; } // SPA fallback serves HTML for missing optional files
  };
  // Both sealed-set generations load: trial face stack (visemes/aus) +
  // main #4 (words/acting). Each doc is optional; timeline is required.
  const [timeline, mouthCues, setPlan, visemesDoc, ausDoc, words, acting] = await Promise.all([
    getJson<TimelineBeat[]>('timeline.json', false),
    getJson<MouthSpan[]>('mouth_cues.json', true),
    getJson<SealedSetInput['setPlan']>('set_plan.json', true),
    getJson<SealedSetInput['visemes']>('visemes.json', true),
    getJson<SealedSetInput['aus']>('aus.json', true),
    getJson<SealedSetInput['words']>('words.json', true),
    getJson<SealedSetInput['acting']>('acting.json', true),
  ]);
  return adaptSealedSet({ ...opts, timeline: timeline ?? [], mouthCues, setPlan, visemes: visemesDoc, aus: ausDoc, words: Array.isArray(words) ? words : undefined, acting: acting && Array.isArray(acting.beats) ? acting : undefined });
}
