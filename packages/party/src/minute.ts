/**
 * Write-a-minute: premise → a ~60 s bit in a character's voice → the human
 * tweaks text + delivery per line → preview on the comedy-club stage → submit
 * as a performance (a funnier.sketch/v1 script, the same schema /sketch plays).
 *
 * The drafter is template-based (original frames, no corpus lines, no API):
 * it reads "<subject> have|are <A> and <B>" premises, builds an opener,
 * three escalating setup → punch → tag beats, a callback to beat one, and a
 * closer with the character's catchphrase. The LLM hook (`draftWith`) can
 * replace it later; nothing here calls a network.
 */
import type { SketchItem, SketchScriptV1, Beat } from '@funnier/sketch';
import type { Delivery } from './jokes';
import type { PartyIdentity } from './identity';
import { mulberry32, pick } from './rng';

export type MinuteRole = 'opener' | 'setup' | 'punch' | 'tag' | 'act-out' | 'callback' | 'closer';
export type LineDelivery = Delivery | 'pause';

export interface MinuteLine {
  id: string;
  beat: number;
  role: MinuteRole;
  text: string;
  delivery: LineDelivery;
  /** Silence before the line (ms). */
  pause_ms: number;
  /** Hold after the line for the laugh (ms, 0 = none). */
  hold_ms: number;
  /** Words to hit (rendered as emphasis in captions; slows them slightly). */
  emphasis: string[];
  /** True once the human has set the emphasis by hand (even to nothing): the agent's re-suggest keeps it. */
  emphasis_user?: boolean;
}

export interface MinuteDraft { schema: 'funnier.minute/v1'; id: string; title: string; premise: string; performer: string; performer_name: string; lines: MinuteLine[] }

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function parsePremise(premise: string): { subject: string; a: string; b: string } {
  const p = premise.trim().replace(/[.!]+$/, '');
  const m = p.match(/^(.+?)\s+(?:have|has|are|is|want|wants)\s+(.+?)\s+and\s+(.+)$/i);
  if (m) return { subject: m[1].toLowerCase(), a: m[2], b: m[3] };
  return { subject: p.toLowerCase(), a: 'big plans', b: 'no follow-through' };
}

/** Rough words → seconds at ~150 wpm plus pauses/holds. */
export function minuteSeconds(lines: MinuteLine[]): number {
  const words = lines.reduce((n, l) => n + l.text.split(/\s+/).filter(Boolean).length, 0);
  return Math.round(words / 2.5 + lines.reduce((n, l) => n + l.pause_ms + l.hold_ms, 0) / 1000);
}

export function draftMinute(premise: string, performer: PartyIdentity, seed = premise): MinuteDraft {
  const rng = mulberry32(`${performer.id}:${seed}`);
  const { subject, a, b } = parsePremise(premise);
  const S = cap(subject);
  // one analogy runs through punch → tag → callback (that is what makes it a callback)
  const ANALOGY = [
    ['Which, to be fair, is also how I would describe a seagull with a phone.', 'At least the seagull says thanks. With its eyes.', 'Meanwhile, the seagull got promoted.'],
    ['So, basically, a toddler with a corporate card.', 'The card is declined. The toddler is not.', 'The toddler now has two cards.'],
    ['Which is also the job description of a cat.', 'The cat, at least, knocks things over quietly.', 'The cat has a manager now. It is me.'],
  ];
  const an = ANALOGY[Math.floor(rng() * ANALOGY.length)];
  const raw: Array<[number, MinuteRole, string]> = [
    [0, 'opener', `Good evening. I'm ${performer.name}. ${pick(rng, ['I help people for a living.', 'I am, professionally, helpful.', 'I work in customer delight. Allegedly.'])}`],
    [1, 'setup', `Tonight I want to talk about ${subject}.`],
    [1, 'setup', `${S} have ${a}, and ${b}.`],
    [1, 'punch', an[0]],
    [1, 'tag', an[1]],
    [2, 'setup', 'It always starts small.'],
    [2, 'act-out', '"Hey, quick one. Can you just—"'],
    [2, 'act-out', '"Also, while you\'re there—"'],
    [2, 'act-out', '"Oh, and one more tiny thing—"'],
    [2, 'punch', 'Forty minutes later I am planning their wedding, and nobody has said please.'],
    [2, 'tag', 'I am not even invited. I am the venue.'],
    [3, 'setup', `People say ${subject} just need clear boundaries.`],
    [3, 'punch', 'I put up a boundary once. They asked me to make it bigger and in landscape.'],
    [3, 'tag', 'Then asked why it was in their way.'],
    [4, 'callback', an[2]],
    [4, 'closer', `${S}: ${a}, ${b}. I love them. ${performer.persona.catchphrase ?? 'Goodnight.'}`],
  ];
  const lines: MinuteLine[] = raw.map(([beat, role, text], i) => ({ id: `l${i + 1}`, beat, role, text, delivery: performer.persona.delivery, pause_ms: 0, hold_ms: 0, emphasis: [] }));
  return { schema: 'funnier.minute/v1', id: `minute-${performer.id.replace(/^[a-z]+\./, '')}-${Math.floor(rng() * 1e6).toString(36)}`, title: cap(premise.replace(/[.!]+$/, '')), premise, performer: performer.id, performer_name: performer.name, lines: suggestDelivery(lines, performer) };
}

/**
 * The agent's delivery suggestions (the human can override any of them).
 * Re-suggesting never overwrites emphasis the human chose (`emphasis_user`).
 */
export function suggestDelivery(lines: MinuteLine[], performer: PartyIdentity): MinuteLine[] {
  return suggestDeliveryRaw(lines, performer).map((l, i) => (lines[i].emphasis_user ? { ...l, emphasis: lines[i].emphasis, emphasis_user: true } : l));
}

function suggestDeliveryRaw(lines: MinuteLine[], performer: PartyIdentity): MinuteLine[] {
  const home = performer.persona.delivery;
  return lines.map((l, i) => {
    const words = l.text.replace(/["—.,!?]/g, '').split(/\s+/).filter((w) => w.length > 2);
    switch (l.role) {
      case 'opener': return { ...l, delivery: 'warm', pause_ms: 0, hold_ms: 0, emphasis: [] };
      case 'setup': return { ...l, delivery: 'deliberate', pause_ms: i > 0 && lines[i - 1].beat !== l.beat ? 400 : 0, hold_ms: 0, emphasis: [] };
      case 'act-out': return { ...l, delivery: 'manic', pause_ms: 150, hold_ms: 0, emphasis: [] };
      case 'punch': return { ...l, delivery: home === 'manic' ? 'manic' : 'deadpan', pause_ms: 700, hold_ms: 1200, emphasis: words.slice(-1) };
      case 'tag': return { ...l, delivery: home === 'warm' ? 'warm' : 'deadpan', pause_ms: 250, hold_ms: 900, emphasis: [] };
      case 'callback': return { ...l, delivery: 'conspiratorial', pause_ms: 600, hold_ms: 1100, emphasis: words.slice(-1) };
      case 'closer': return { ...l, delivery: home, pause_ms: 500, hold_ms: 1500, emphasis: [] };
    }
  });
}

const EMOTION: Record<LineDelivery, string> = { deadpan: 'neutral', deliberate: 'relaxed', manic: 'surprised', warm: 'happy', conspiratorial: 'relaxed', pause: 'neutral' };
const KIND: Record<number, Beat['kind']> = { 0: 'setup', 1: 'game', 2: 'escalation', 3: 'turn', 4: 'button' };

/** Minute → funnier.sketch/v1 on the comedy-club stage (one performer at the mic). */
export function minuteToSketch(m: MinuteDraft, avatar_url = 'basic'): SketchScriptV1 {
  const beats: Beat[] = [];
  for (const l of m.lines) {
    let beat = beats.find((b) => b.id === `b${l.beat}`);
    if (!beat) { beat = { id: `b${l.beat}`, kind: KIND[l.beat] ?? 'game', items: [] }; beats.push(beat); }
    const items: SketchItem[] = beat.items;
    if (l.pause_ms > 0) items.push({ type: 'pause', ms: l.pause_ms });
    if (l.delivery === 'pause') continue;
    if (l.delivery === 'manic') items.push({ type: 'gesture', who: 'comic', kind: 'open', intensity: 0.9 });
    if (l.role === 'punch' && l.delivery === 'deadpan') items.push({ type: 'look', who: 'comic', at: 'camera', ms: 900 });
    const text = l.emphasis.length ? l.text.replace(new RegExp(`\\b(${l.emphasis.map((w) => w.replace(/[^\w']/g, '')).filter(Boolean).join('|')})\\b`, 'g'), (w) => w.toUpperCase()) : l.text;
    items.push({ type: 'line', who: 'comic', text, emotion: EMOTION[l.delivery], id: l.id });
    if (l.hold_ms > 0) items.push({ type: 'hold_for_laugh', ms: l.hold_ms });
  }
  beats.at(-1)?.items.push({ type: 'button' });
  return {
    schema: 'funnier.sketch/v1', id: m.id, title: m.title, set: 'comedy-club', premise: m.premise,
    credits: `Original minute drafted by ${m.performer_name} (template drafter), edited in write-a-minute.`,
    cast: [{ role: 'comic', identity: m.performer, seat: 'stage', name: m.performer_name, avatar_url }],
    scenes: [{ id: 's1', title: m.title, beats }],
  };
}

/** A submitted minute: the performance (sketch) + the editable minute it came from. */
export interface MinuteSubmission { schema: 'funnier.minute-submission/v1'; submitted_at: string; minute: MinuteDraft; performance: SketchScriptV1; seconds: number }

export function submitMinute(m: MinuteDraft, avatar_url: string, at = new Date().toISOString()): MinuteSubmission {
  return { schema: 'funnier.minute-submission/v1', submitted_at: at, minute: m, performance: minuteToSketch(m, avatar_url), seconds: minuteSeconds(m.lines) };
}
