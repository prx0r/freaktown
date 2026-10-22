/**
 * The set writer. Template-based and deterministic: it places the theory's
 * material kernels (best premise match first, ordered as a UCB game: establish
 * → heighten → explore → top), fills the time with premise frames built from
 * the character's game and props, adds attitude segues, a callback to the
 * first bit and a closer on the catchphrase. Lines are setup / punch / tag /
 * act-out / callback, i.e. the party MinuteLine roles, so a set becomes a
 * funnier.sketch/v1 performance through the existing minute pipeline.
 *
 * LLM hook: OFF. setLlmHook(fn) lets a caller inject a completion function
 * that returns extra kernels as JSON; nothing in this package makes a network
 * call or spends money.
 */
import { minuteSeconds, mulberry32, parsePremise, pick, type MinuteRole, type Rng } from '@funnier/party';
import { suggestSetDelivery } from './delivery';
import { SET_SCHEMA, type CharacterSet, type CharacterTheory, type MaterialKernel, type SetBeat, type SetLine } from './types';

export type LlmHook = (prompt: string) => string | null;
let LLM: LlmHook | null = null;
/** Turn the LLM hook on (inject a completion fn) or off (null). Off by default. */
export function setLlmHook(fn: LlmHook | null): void { LLM = fn; }
export function llmEnabled(): boolean { return LLM !== null; }

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const words = (s: string) => s.toLowerCase().match(/[a-z']+/g) ?? [];
const STOP = new Set(['the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'is', 'are', 'have', 'has', 'with', 'for', 'it', 'they', 'their', 'want', 'wants', 'about', 'that', 'who', 'what']);

/** Relevance of a kernel to a premise (keyword + topic overlap). */
export function kernelScore(k: MaterialKernel, premise: string): number {
  const p = new Set(words(premise).filter((w) => !STOP.has(w)));
  const kw = [...k.keywords.flatMap(words), ...words(k.topic)].filter((w) => !STOP.has(w));
  let s = 0;
  for (const w of kw) if (p.has(w) || [...p].some((x) => x.length > 3 && (x.startsWith(w) || w.startsWith(x)))) s += 1;
  return s;
}

/** Premise frames: original templates that turn "<subject> have <a> and <b>" into bits, flavoured by the theory. */
export function premiseKernels(t: CharacterTheory, premise: string, rng: Rng): MaterialKernel[] {
  const { subject, a, b } = parsePremise(premise);
  const S = cap(subject);
  const prop = t.props[0] ?? 'the job';
  const prop2 = t.props[1] ?? prop;
  const att = t.point_of_view.attitude[0] ?? 'weird';
  const misread = t.flaw.misreads[0];
  const out: MaterialKernel[] = [
    {
      id: 'frame-establish', topic: subject, keywords: words(subject), attitude: att, premise: `${subject} are ${att}`, mechanism: t.writes[0] ?? 'observational', move: 'establish',
      setups: [`You know what is ${att} about ${subject}?`, `${S} have ${a}, and ${b}.`],
      punch: `Which is exactly how I would describe ${prop}.`, tags: [`At least ${prop} stays where you put it.`],
      callback: `${S}. Still ${a}. Still ${b}. Still less reliable than ${prop}.`,
    },
    {
      id: 'frame-escalate', topic: `${subject}, escalating`, keywords: words(subject), attitude: att, premise: `${subject} never ask for one thing`, mechanism: t.writes[0] ?? 'observational', move: 'heighten',
      setups: ['It always starts small.'], act_out: ['"Quick one. Could you just—"', '"Also, while you are there—"', '"Oh, and one more tiny thing—"'],
      punch: `An hour later I am still there, next to ${prop2}, and nobody remembers what the first thing was.`, tags: [`It was ${a}. It is always ${a}.`],
    },
  ];
  if (misread) {
    out.push({
      id: 'frame-misread', topic: `${subject}, misread`, keywords: words(subject), attitude: att, premise: t.flaw.misinterpretation_rule, mechanism: 'misdirection', move: 'explore',
      setups: [`People say ${subject} come with ${misread.trigger}.`], punch: `I hear ${misread.trigger}. I think: ${misread.as}.`, tags: [pick(rng, [`That is the kind of ${misread.as.replace(/^(a|an|the) /, '')} I can work with.`, `My friends call that a problem. I call it ${misread.as}, with paperwork.`])],
    });
  }
  out.push(
    {
      id: 'frame-status', topic: `${subject}, status`, keywords: words(subject), attitude: 'unfair', premise: t.status.see_saw, mechanism: 'self-deprecating', move: 'heighten',
      setups: [`In my head, I am ${t.status.felt.replace(/^(a|an|the) /i, 'the ')}.`], punch: `On paper, I am ${t.status.actual}.`, tags: [`${S} can tell. ${S} can always tell.`],
    },
    {
      id: 'frame-want', topic: `${subject}, want`, keywords: words(subject), attitude: 'hard', premise: t.comic_want, mechanism: t.writes[0] ?? 'observational', move: 'explore',
      setups: [`You know what I actually want?`, `${cap(t.comic_want.replace(/^to /, 'to '))}.`], punch: `Instead, I get ${subject}. ${cap(a)}. ${cap(b)}.`, tags: ['I am not complaining. I am keeping a list.'],
    },
    {
      id: 'frame-contradiction', topic: `${subject}, contradiction`, keywords: words(subject), attitude: 'weird', premise: t.contradictions[0] ?? 'a contradiction', mechanism: 'self-deprecating', move: 'explore',
      setups: ['People say I am a walking contradiction.'], punch: `${cap((t.contradictions[0] ?? 'helpful, and no help at all').replace(/[.]$/, ''))}. Guilty.`, tags: ['I would argue, but that would be another one.'],
    },
    {
      id: 'frame-worldview', topic: `${subject}, worldview`, keywords: words(subject), attitude: att, premise: t.worldview.causality, mechanism: 'deadpan', move: 'top',
      setups: ['Here is what I believe.', t.worldview.causality], punch: `So when ${subject} come to me with ${a}, I stay calm. I simply blame ${prop}.`, tags: [`${cap(prop)} has never once defended itself. Suspicious.`],
    },
  );
  out.push({
    id: 'frame-boundary', topic: `${subject}, boundaries`, keywords: words(subject), attitude: 'hard', premise: `${subject} ignore every boundary`, mechanism: 'absurd', move: 'top',
    setups: [`People say ${subject} just need clear boundaries.`], punch: `I tried that. I put up a boundary. Somebody leaned ${prop} against it.`, tags: ['Then asked me to move it, because it was in the way.'],
  });
  return out;
}

const MOVE_ORDER: Record<MaterialKernel['move'], number> = { establish: 0, heighten: 1, explore: 2, top: 3 };

export interface WriteOptions { length_min: 1 | 3 | 5; seed?: string; at: string; title?: string; by?: string }

let lineSeq = 0;
const mkLine = (beat: number, role: MinuteRole, text: string, source: string, t: CharacterTheory, extra: Partial<SetLine> = {}): SetLine => ({
  id: `l${++lineSeq}`, beat, role, text, delivery: t.physicality.delivery_default, pause_ms: 0, hold_ms: 0, emphasis: [], source, ...extra,
});

function kernelLines(k: MaterialKernel, beat: number, t: CharacterTheory, segue?: string): SetLine[] {
  const L: SetLine[] = [];
  if (segue) L.push(mkLine(beat, 'setup', segue, 'segue', t));
  for (const s of k.setups) L.push(mkLine(beat, 'setup', s, k.id, t));
  for (const a of k.act_out ?? []) L.push(mkLine(beat, 'act-out', a, k.id, t));
  L.push(mkLine(beat, 'punch', k.punch, k.id, t, { mechanism: k.mechanism }));
  for (const g of k.tags) L.push(mkLine(beat, 'tag', g, k.id, t, { mechanism: k.mechanism }));
  return L;
}

function renumber(lines: SetLine[]): SetLine[] { return lines.map((l, i) => ({ ...l, id: `l${i + 1}` })); }

/** Optional extra kernels from the LLM hook (only when it is on). */
function llmKernels(t: CharacterTheory, premise: string): MaterialKernel[] {
  if (!LLM) return [];
  const out = LLM(`Write 3 ORIGINAL stand-up joke kernels for the character "${t.name}" (${t.logline}). Premise: "${premise}". Voice: ${t.voice.register}. Game: ${t.game.pattern}. Return JSON [{"topic":"","setups":[""],"punch":"","tags":[""]}]. No existing jokes.`);
  try {
    const arr = JSON.parse(out ?? '[]') as Array<{ topic: string; setups: string[]; punch: string; tags?: string[] }>;
    return arr.filter((x) => x.punch && x.setups?.length).map((x, i) => ({ id: `llm-${i + 1}`, topic: x.topic, keywords: words(x.topic), attitude: t.point_of_view.attitude[0], premise: x.topic, setups: x.setups, punch: x.punch, tags: x.tags ?? [], mechanism: t.writes[0], move: 'heighten' as const }));
  } catch { return []; }
}

/** set.write: premise + length (1/3/5 min) → a structured set in the character's voice. */
export function writeSet(t: CharacterTheory, premise: string, o: WriteOptions): CharacterSet {
  lineSeq = 0;
  const seed = o.seed ?? premise;
  const rng = mulberry32(`${t.id}:set:${seed}:${o.length_min}`);
  const target = o.length_min * 60;
  const opener = t.material.find((k) => k.topic === 'opener');
  const closer = t.material.find((k) => k.topic === 'closer');
  const pool = [...t.material.filter((k) => k !== opener && k !== closer), ...llmKernels(t, premise), ...premiseKernels(t, premise, rng)];
  // rank: authored kernels first (by premise relevance), frames only fill what is left
  const ranked = pool.map((k, i) => ({ k, s: (k.id.startsWith('frame-') ? 0.6 + Math.min(1, kernelScore(k, premise)) * 0.3 : 1 + kernelScore(k, premise)) + rng() * 0.05, i }))
    .sort((x, y) => y.s - x.s || x.i - y.i);

  const lines: SetLine[] = [];
  const beats: SetBeat[] = [];
  let beat = 0;
  // opener
  if (opener) lines.push(...kernelLines(opener, beat, t));
  else {
    const intro = (t.intro ?? t.premise.split(/\s+(?:who|that)\s+|;/i)[0]).replace(/^(A|An|The)\b/, (m) => m.toLowerCase());
    lines.push(mkLine(beat, 'opener', `Good evening. I am ${t.name}, ${intro}.`, 'frame-opener', t));
    if (t.voice.verbal_tics[0]) lines.push(mkLine(beat, 'tag', t.voice.verbal_tics[0], 'frame-opener', t));
  }
  if (opener) lines[0].role = 'opener';
  beats.push({ n: beat, kind: 'opener', topic: 'opener', move: 'open', source: opener?.id ?? 'frame-opener' });

  // body: take kernels until the time is filled, leaving room for callback + closer
  const closerBudget = 22;
  const chosen: MaterialKernel[] = [];
  let acc: SetLine[] = [...lines];
  for (const { k } of ranked) {
    const trial = [...acc, ...kernelLines(k, 99, t)];
    const secs = minuteSeconds(suggestSetDelivery(trial, t));
    if (secs > target - closerBudget + 8 && chosen.length > 0) continue;
    chosen.push(k);
    acc = trial;
    if (secs >= target - closerBudget - 6) break;
  }
  // order the chosen kernels as a game: the best match establishes, then heighten → explore → top
  const first = chosen.find((k) => k.move === 'establish') ?? chosen[0];
  const rest = chosen.filter((k) => k !== first).sort((x, y) => MOVE_ORDER[x.move] - MOVE_ORDER[y.move]);
  const ordered = first ? [first, ...rest] : [];
  const att = t.point_of_view.attitude;
  ordered.forEach((k, i) => {
    beat += 1;
    const a2 = att[(i / 2) % att.length | 0] ?? 'weird';
    const segue = i > 0 && i % 2 === 0 ? [`And you know what else is ${a2}?`, `Here is something ${a2}.`, `You want ${a2}? I will give you ${a2}.`][(i / 2 - 1) % 3] : undefined;
    lines.push(...kernelLines(k, beat, t, segue));
    beats.push({ n: beat, kind: 'bit', topic: k.topic, move: k.move, source: k.id });
  });

  // callback to the first bit that offers one
  const cb = ordered.find((k) => k.callback);
  if (cb) {
    beat += 1;
    lines.push(mkLine(beat, 'callback', cb.callback!, `callback:${cb.id}`, t, { callback_to: cb.id }));
    beats.push({ n: beat, kind: 'callback', topic: cb.topic, move: 'top', source: cb.id });
  }
  // closer
  beat += 1;
  if (closer) lines.push(...kernelLines(closer, beat, t).map((l, i, a) => (i === a.length - 1 ? { ...l, role: 'closer' as MinuteRole } : l)));
  else lines.push(mkLine(beat, 'closer', `All I want is ${t.comic_want.replace(/[.]$/, '')}. Tonight, I got close. ${t.catchphrases[0] ?? 'Goodnight.'}`, 'frame-closer', t));
  beats.push({ n: beat, kind: 'closer', topic: 'closer', move: 'close', source: closer?.id ?? 'frame-closer' });

  const final = suggestSetDelivery(renumber(lines), t);
  const set: CharacterSet = {
    schema: SET_SCHEMA,
    id: `set-${t.id.replace(/^[a-z]+\./, '')}-${o.length_min}m-${Math.floor(rng() * 36 ** 4).toString(36).padStart(4, '0')}`,
    character: t.id, character_name: t.name, title: o.title ?? cap(premise.replace(/[.!]+$/, '')), premise, length_min: o.length_min,
    target_seconds: target, seconds: minuteSeconds(final), seed, generator: LLM ? 'llm' : 'template', beats, lines: final, revisions: [], status: 'draft',
  };
  return set;
}

// ── set.revise ───────────────────────────────────────────────────────────

const FILLER = /\b(basically|actually|really|just|honestly|literally|very)\b,?\s*/gi;

/**
 * Apply writer's-room notes. One note per line or separated by ";". Understood:
 *   cut l7 | cut beat 3 | replace l7: <text> | tag l7: <text> (insert a tag after l7)
 *   swap beats 2 4 | move beat 5 to 2 | tighten | slower | faster
 *   more <deadpan|manic|warm|deliberate|conspiratorial> (punch deliveries)
 *   punch up beat 3 (promote the best tag to the punch) | add callback
 * Anything else is recorded as unhandled (honest; nothing is invented).
 */
export function reviseSet(s: CharacterSet, t: CharacterTheory, notes: string, at: string): { set: CharacterSet; changes: string[]; unhandled: string[] } {
  let lines = s.lines.map((l) => ({ ...l }));
  let beats = s.beats.map((b) => ({ ...b }));
  const changes: string[] = [];
  const unhandled: string[] = [];
  const find = (id: string) => lines.findIndex((l) => l.id === id);
  for (const raw of notes.split(/\n|;/).map((x) => x.trim()).filter(Boolean)) {
    let m: RegExpMatchArray | null;
    if ((m = raw.match(/^cut\s+(l\d+)$/i))) { const i = find(m[1]); if (i >= 0) { changes.push(`cut ${m[1]}: "${lines[i].text}"`); lines.splice(i, 1); } else unhandled.push(raw); }
    else if ((m = raw.match(/^cut\s+beat\s+(\d+)$/i))) { const n = +m[1]; const before = lines.length; lines = lines.filter((l) => l.beat !== n); beats = beats.filter((b) => b.n !== n); changes.push(`cut beat ${n} (${before - lines.length} lines)`); }
    else if ((m = raw.match(/^replace\s+(l\d+)\s*:\s*(.+)$/i))) { const i = find(m[1]); if (i >= 0) { changes.push(`replace ${m[1]}: "${lines[i].text}" → "${m[2]}"`); lines[i] = { ...lines[i], text: m[2], source: 'note' }; } else unhandled.push(raw); }
    else if ((m = raw.match(/^tag\s+(l\d+)\s*:\s*(.+)$/i))) { const i = find(m[1]); if (i >= 0) { lines.splice(i + 1, 0, { ...lines[i], id: `${m[1]}t`, role: 'tag', text: m[2], source: 'note', emphasis: [] }); changes.push(`tag after ${m[1]}: "${m[2]}"`); } else unhandled.push(raw); }
    else if ((m = raw.match(/^swap\s+beats?\s+(\d+)\s+(?:and\s+)?(\d+)$/i))) {
      const [x, y] = [+m[1], +m[2]];
      const blockX = lines.filter((l) => l.beat === x), blockY = lines.filter((l) => l.beat === y);
      if (!blockX.length || !blockY.length) { unhandled.push(raw); continue; }
      const out: SetLine[] = []; let doneX = false, doneY = false;
      for (const l of lines) {
        if (l.beat === x) { if (!doneX) { out.push(...blockY.map((b) => ({ ...b, beat: x }))); doneX = true; } continue; }
        if (l.beat === y) { if (!doneY) { out.push(...blockX.map((b) => ({ ...b, beat: y }))); doneY = true; } continue; }
        out.push(l);
      }
      lines = out;
      beats = beats.map((b) => (b.n === x ? { ...beats.find((q) => q.n === y)!, n: x } : b.n === y ? { ...s.beats.find((q) => q.n === x)!, n: y } : b));
      changes.push(`swapped beats ${x} and ${y}`);
    }
    else if (/^tighten$/i.test(raw)) {
      let n = 0;
      lines = lines.map((l) => { if (l.role === 'act-out') return l; const txt = l.text.replace(FILLER, '').replace(/\s{2,}/g, ' '); if (txt !== l.text) n++; return { ...l, text: txt.charAt(0).toUpperCase() + txt.slice(1) }; });
      // drop segues (attitude lead-ins) once the act is moving: Carter's "cut the attitude words, keep the attitude"
      const segues = lines.filter((l) => l.source === 'segue').length;
      lines = lines.filter((l) => l.source !== 'segue');
      changes.push(`tightened: filler removed from ${n} lines, ${segues} attitude segues cut`);
    }
    else if (/^(slower|more pauses)$/i.test(raw)) { lines = lines.map((l) => (l.role === 'punch' || l.role === 'callback' ? { ...l, pause_ms: l.pause_ms + 250, hold_ms: l.hold_ms + 200 } : l)); changes.push('slower: +250 ms before punches, +200 ms holds'); }
    else if (/^faster$/i.test(raw)) { lines = lines.map((l) => ({ ...l, pause_ms: Math.max(0, l.pause_ms - 200), hold_ms: Math.max(0, l.hold_ms - 200) })); changes.push('faster: -200 ms pauses and holds'); }
    else if ((m = raw.match(/^more\s+(deadpan|manic|warm|deliberate|conspiratorial)$/i))) { const d = m[1].toLowerCase() as SetLine['delivery']; lines = lines.map((l) => (l.role === 'punch' || l.role === 'tag' ? { ...l, delivery: d } : l)); changes.push(`punches and tags now ${d}`); }
    else if ((m = raw.match(/^punch\s*up\s+beat\s+(\d+)$/i))) {
      const n = +m[1];
      const pi = lines.findIndex((l) => l.beat === n && l.role === 'punch');
      const tags = lines.map((l, i) => ({ l, i })).filter((x) => x.l.beat === n && x.l.role === 'tag');
      if (pi < 0 || !tags.length) { unhandled.push(raw); continue; }
      const best = tags.reduce((a, b) => (b.l.text.length < a.l.text.length ? b : a)); // shortest tag = tightest punch
      const oldPunch = lines[pi].text;
      lines[pi] = { ...lines[pi], text: best.l.text, source: `${lines[pi].source}+punchup` };
      lines[best.i] = { ...lines[best.i], text: oldPunch };
      changes.push(`punched up beat ${n}: tag "${best.l.text}" promoted to punch`);
    }
    else if (/^add\s+callback$/i.test(raw)) {
      if (lines.some((l) => l.role === 'callback')) { changes.push('callback already present'); continue; }
      const first = t.material.find((k) => k.callback && lines.some((l) => l.source === k.id));
      if (!first) { unhandled.push(`${raw} (no placed kernel offers a callback)`); continue; }
      const ci = lines.findIndex((l) => l.role === 'closer');
      const closerBeat = ci >= 0 ? lines[ci].beat : (lines.at(-1)?.beat ?? 0) + 1;
      lines.splice(ci >= 0 ? ci : lines.length, 0, { id: 'cb', beat: closerBeat, role: 'callback', text: first.callback!, delivery: t.physicality.delivery_default, pause_ms: 600, hold_ms: t.physicality.punchline_hold_ms, emphasis: [], source: `callback:${first.id}`, callback_to: first.id });
      changes.push(`added callback to ${first.id}`);
    }
    else unhandled.push(raw);
  }
  const keepTiming = !/slower|faster|more pauses/i.test(notes);
  const renum = renumber(lines);
  const next = keepTiming ? renum.map((l) => (l.source === 'note' ? suggestSetDelivery([l], t)[0] : l)) : renum;
  const set: CharacterSet = { ...s, lines: next, beats, seconds: minuteSeconds(next), status: 'revised', revisions: [...s.revisions, { at, notes, changes: [...changes, ...unhandled.map((u) => `UNHANDLED: ${u}`)] }] };
  return { set, changes, unhandled };
}

/** Plain-text script of a set (what goes in sets/<id>.md). */
export function setToText(s: CharacterSet): string {
  const head = `# ${s.title}\n\n${s.character_name} · ${s.length_min}-minute set · ~${s.seconds}s (target ${s.target_seconds}s) · ${s.status} · generator: ${s.generator}\n\nPremise: ${s.premise}\n`;
  let cur = -1;
  const body = s.lines.map((l) => {
    const b = s.beats.find((x) => x.n === l.beat);
    const hdr = l.beat !== cur ? `\n## Beat ${l.beat}: ${b?.kind ?? ''}${b && b.kind === 'bit' ? ` · ${b.topic} · ${b.move}` : ''}\n\n` : '';
    cur = l.beat;
    const cue = [l.delivery, l.pause_ms ? `pause ${l.pause_ms}` : '', l.hold_ms ? `hold ${l.hold_ms}` : '', l.emphasis.length ? `hit: ${l.emphasis.join(' ')}` : ''].filter(Boolean).join(', ');
    return `${hdr}- **${l.role.toUpperCase()}** (${l.id}) ${l.text}  _[${cue}]_`;
  }).join('\n');
  const rev = s.revisions.length ? `\n\n## Revisions\n\n${s.revisions.map((r, i) => `${i + 1}. ${r.at.slice(0, 16)} · notes: "${r.notes.replace(/\n/g, '; ')}"\n${r.changes.map((c) => `   - ${c}`).join('\n')}`).join('\n')}` : '';
  return `${head}${body}${rev}\n`;
}
