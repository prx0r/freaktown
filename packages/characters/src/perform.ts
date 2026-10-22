/**
 * Performance: a set → the party MinuteDraft → funnier.sketch/v1 (comedy-club
 * stage, one performer at the mic), compiled to stage events for preview.
 */
import { minuteToSketch, submitMinute, type MinuteDraft, type MinuteSubmission, type PartyIdentity } from '@funnier/party';
import { compileSketch, validateSketch, type SketchScriptV1 } from '@funnier/sketch';
import type { CharacterSet } from './types';

export function setToMinute(s: CharacterSet): MinuteDraft {
  return {
    schema: 'funnier.minute/v1', id: s.id, title: s.title, premise: s.premise, performer: s.character, performer_name: s.character_name,
    lines: s.lines.map((l) => ({ id: l.id, beat: l.beat, role: l.role, text: l.text, delivery: l.delivery, pause_ms: l.pause_ms, hold_ms: l.hold_ms, emphasis: l.emphasis })),
  };
}

export function setToSketch(s: CharacterSet, idn: Pick<PartyIdentity, 'look'>): SketchScriptV1 {
  const sk = minuteToSketch(setToMinute(s), idn.look.avatar_url);
  sk.credits = `Original ${s.length_min}-minute set by ${s.character_name}, written with the /characters3 studio (${s.generator} writer${s.revisions.length ? `, ${s.revisions.length} revision(s)` : ''}).`;
  return sk;
}

export function submitSet(s: CharacterSet, idn: Pick<PartyIdentity, 'look'>, at: string): MinuteSubmission & { problems: string[] } {
  const sub = submitMinute(setToMinute(s), idn.look.avatar_url, at);
  sub.performance.credits = setToSketch(s, idn).credits;
  return { ...sub, problems: validateSketch(sub.performance) };
}

export interface PreviewEvents { sketch_id: string; duration_ms: number; timing_source: string; events: Array<{ t_ms: number; type: string; payload: Record<string, unknown> }>; warnings: string[] }

/** Stage events (the same timeline /sketch plays) for a set; `limit` trims the list for transport. */
export function previewEvents(s: CharacterSet, idn: Pick<PartyIdentity, 'look'>, limit = 400): PreviewEvents {
  const c = compileSketch(setToSketch(s, idn));
  return { sketch_id: c.sketch_id, duration_ms: c.duration_ms, timing_source: c.timing_source, events: c.events.slice(0, limit) as PreviewEvents['events'], warnings: c.warnings ?? [] };
}
