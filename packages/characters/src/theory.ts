/**
 * Theory helpers: validate, patch (deep merge with a changelog), render the
 * per-character THEORY.md, and map to the characters3 seed vocabulary.
 */
import { DELIVERIES, MECHANISMS } from '@funnier/party';
import { THEORY_SCHEMA, type Attitude, type CharacterTheory } from './types';

export const ATTITUDES: readonly Attitude[] = ['weird', 'hard', 'scary', 'stupid', 'wonderful', 'unfair'];

const str = (x: unknown) => typeof x === 'string' && x.trim().length > 0;
const arr = (x: unknown, min = 0) => Array.isArray(x) && x.length >= min;

/** Every problem with a theory, as human-readable strings (empty = valid). */
export function validateTheory(t: CharacterTheory): string[] {
  const p: string[] = [];
  if (t?.schema !== THEORY_SCHEMA) p.push(`schema must be ${THEORY_SCHEMA}`);
  if (!/^[a-z0-9][a-z0-9.-]{2,48}$/.test(t?.id ?? '')) p.push('id: lowercase identity id');
  for (const k of ['name', 'logline', 'premise', 'comic_want', 'need', 'humanity'] as const) if (!str(t?.[k])) p.push(`${k} required`);
  if (!str(t?.flaw?.flaw) || !str(t?.flaw?.blind_spot) || !str(t?.flaw?.misinterpretation_rule)) p.push('flaw.flaw / blind_spot / misinterpretation_rule required');
  if (!['high', 'low', 'shifting'].includes(t?.status?.plays)) p.push('status.plays: high|low|shifting');
  if (!arr(t?.point_of_view?.attitude, 1) || t.point_of_view.attitude.some((a) => !ATTITUDES.includes(a))) p.push(`point_of_view.attitude: ${ATTITUDES.join('|')}`);
  if (!str(t?.game?.unusual_thing) || !str(t?.game?.pattern) || !arr(t?.game?.heighten, 1)) p.push('game.unusual_thing / pattern / heighten[] required');
  if (!t?.voice || typeof t.voice.max_sentence_words !== 'number') p.push('voice.max_sentence_words required');
  if (!DELIVERIES.includes(t?.physicality?.delivery_default)) p.push('physicality.delivery_default: a party Delivery');
  if (!t?.taste || typeof t.taste.composure !== 'number') p.push('taste.composure required');
  if (!arr(t?.writes, 1) || t.writes.some((m) => !MECHANISMS.includes(m))) p.push('writes: party mechanisms');
  for (const k of ['ontology', 'epistemology', 'axiology', 'causality', 'agency'] as const) if (!str(t?.worldview?.[k])) p.push(`worldview.${k} required`);
  if (!arr(t?.taboo?.safety_rails, 1)) p.push('taboo.safety_rails: at least one rail');
  if (!arr(t?.catchphrases)) p.push('catchphrases[] required (may be empty)');
  for (const k of t?.material ?? []) {
    if (!str(k.id) || !str(k.punch) || !arr(k.setups, 1)) p.push(`material ${k.id ?? '?'}: id, setups[1+], punch`);
    if (!MECHANISMS.includes(k.mechanism)) p.push(`material ${k.id}: mechanism`);
  }
  const ids = new Set<string>();
  for (const k of t?.material ?? []) { if (ids.has(k.id)) p.push(`material ${k.id}: duplicate id`); ids.add(k.id); }
  return p;
}

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);

/**
 * Deep-merge a patch into a theory. Objects merge, arrays and scalars replace,
 * except `material`, `callbacks` and `relationships`, which upsert by id/who
 * (so update_theory can add one kernel without resending the rest). A value of
 * null deletes the key. `replace` lists top-level keys to replace wholesale
 * instead of upserting. Appends a changelog entry.
 */
export function patchTheory(t: CharacterTheory, patch: Record<string, unknown>, by: string, note: string, at: string, replace: string[] = []): CharacterTheory {
  const out = structuredClone(t) as unknown as Record<string, unknown>;
  const upsertKey: Record<string, string> = { material: 'id', callbacks: 'id', relationships: 'who' };
  const merge = (dst: Record<string, unknown>, src: Record<string, unknown>, path: string) => {
    for (const [k, v] of Object.entries(src)) {
      const here = path ? `${path}.${k}` : k;
      if (v === null) { delete dst[k]; continue; }
      if (!path && upsertKey[k] && Array.isArray(v) && !replace.includes(k)) {
        const key = upsertKey[k];
        const cur = (Array.isArray(dst[k]) ? dst[k] : []) as Array<Record<string, unknown>>;
        for (const item of v as Array<Record<string, unknown>>) {
          const i = cur.findIndex((c) => c[key] === item[key]);
          if (item._delete) { if (i >= 0) cur.splice(i, 1); continue; }
          if (i >= 0) cur[i] = { ...cur[i], ...item }; else cur.push(item);
        }
        dst[k] = cur;
      } else if (isObj(v) && isObj(dst[k])) merge(dst[k] as Record<string, unknown>, v, here);
      else dst[k] = structuredClone(v);
    }
  };
  const { changelog: _ignored, schema: _s, id: _i, ...rest } = patch;
  merge(out, rest, '');
  const res = out as unknown as CharacterTheory;
  res.changelog = [...(t.changelog ?? []), { at, by, note }];
  return res;
}

const bullet = (xs: string[]) => (xs.length ? xs.map((x) => `- ${x}`).join('\n') : '- _(none yet)_');

/** The per-character theory doc (generated; the JSON is the source of truth). */
export function renderTheoryMarkdown(t: CharacterTheory): string {
  const w = t.worldview;
  const taste = Object.entries(t.taste.weights).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0)).map(([m, v]) => `${m} ${(v ?? 0) >= 0 ? '+' : ''}${(v ?? 0).toFixed(2)}`).join(', ');
  const arc = t.arc.stages.map((s) => `${s.n}. **${s.title}** (${s.status}): ${s.shift}`).join('\n');
  const mat = t.material.map((k) => `- \`${k.id}\` · ${k.topic} · ${k.attitude} · ${k.move} · ${k.mechanism}: _${k.premise}_`).join('\n');
  return `# ${t.name}: character theory

> Generated from \`theory.json\` (${t.schema}). Edit the JSON (or call \`character_update_theory\`), not this file.
> Craft vocabulary: see docs/CHARACTER-THEORY.md.

**Logline.** ${t.logline}

**Premise.** ${t.premise}

## Want, need, flaw

- **Comic want** (what they chase on stage): ${t.comic_want}
- **Need** (what they can't see they need): ${t.need}
- **Flaw:** ${t.flaw.flaw}
- **Blind spot:** ${t.flaw.blind_spot}
- **Misinterpretation rule:** ${t.flaw.misinterpretation_rule}
${t.flaw.misreads.map((m) => `  - hears _${m.trigger}_ as _${m.as}_`).join('\n')}

## Status

- **Plays** ${t.status.plays} to other characters, **${t.status.to_audience}** to the audience.
- **Felt status:** ${t.status.felt}. **Actual status:** ${t.status.actual}.
- **See-saw** (how the status tips and gets the laugh): ${t.status.see_saw}

## Point of view

- **Attitude:** ${t.point_of_view.attitude.join(', ')}
- **Take:** ${t.point_of_view.take}
- **Lens:** ${t.point_of_view.lens}

## The game of the character

- **Base reality:** ${t.game.base_reality}
- **First unusual thing:** ${t.game.unusual_thing}
- **Pattern:** ${t.game.pattern}
- **Heighten** (if this is true, what else is true?):
${t.game.heighten.map((x) => `  - ${x}`).join('\n')}
- **Explore** (if this is true, why?):
${t.game.explore.map((x) => `  - ${x}`).join('\n')}

## Voice

- **Register:** ${t.voice.register}
- **Sentence shape:** ${t.voice.sentence_shape} (flag over ${t.voice.max_sentence_words} words)
- **Contractions:** ${t.voice.contractions}. **Exclamations:** ${t.voice.exclamations ? 'allowed' : 'never'}.
- **Verbal tics:** ${t.voice.verbal_tics.map((x) => `"${x}"`).join(', ') || '_none_'}
- **Signature words:** ${t.voice.signature_words.join(', ') || '_none_'}
- **Never in this voice:** ${t.voice.forbidden_words.join(', ') || '_none_'}
${Object.keys(t.voice.substitutions).length ? `- **Substitutions:** ${Object.entries(t.voice.substitutions).map(([a, b]) => `${a} → ${b}`).join('; ')}` : ''}

## Physicality and delivery defaults

- **Default delivery:** ${t.physicality.delivery_default} · energy ${t.physicality.energy} · pace ${t.physicality.pace} · holds ${t.physicality.punchline_hold_ms} ms after a punch
- **Stillness:** ${t.physicality.stillness}
- **Gestures:** ${t.physicality.gestures.join('; ') || '_none_'}

## Taste (what makes them smile, used by Try-Not-To-Smile)

- **Weights:** ${taste}
- **Composure** ${t.taste.composure} · volatility ${t.taste.volatility} · reacts after ${t.taste.reaction_ms} ms
- **Smiles at:**
${bullet(t.taste.smiles_at)}
- **Stone face at:**
${bullet(t.taste.stone_face_at)}
- **Writes in:** ${t.writes.join(', ')}

## Worldview

- **Ontology** (what the world is): ${w.ontology}
- **Epistemology** (how they know things): ${w.epistemology}
- **Axiology** (what is good): ${w.axiology}
- **Causality** (why things happen): ${w.causality}
- **Agency** (what one can change): ${w.agency}

## Contradictions

${bullet(t.contradictions)}

## Backstory anchors

${bullet(t.backstory_anchors)}

## Catchphrases and callbacks

${bullet(t.catchphrases.map((c) => `"${c}"`))}

**Runners:**
${bullet(t.callbacks.map((c) => `\`${c.id}\`: ${c.runner} (seed: "${c.seed_line}")`))}

## Relationships

${bullet(t.relationships.map((r) => `**${r.who}**${r.identity ? ` (\`${r.identity}\`)` : ''}: ${r.dynamic}${r.metaphor ? `. Metaphor: ${r.metaphor}` : ''}. Status: ${r.status}.`))}

## Humanity

${t.humanity}

## Taboo lines and safety rails

- **Never targets:** ${t.taboo.never_targets.join('; ') || '_none_'}
- **Never topics:** ${t.taboo.never_topics.join('; ') || '_none_'}
- **Never says:** ${t.taboo.never_says.map((x) => `"${x}"`).join(', ') || '_none_'}
- **Rails:**
${bullet(t.taboo.safety_rails)}

## Arc across appearances (${t.arc.shape})

${arc}

**Reset rule:** ${t.arc.reset_rule}

**Appearances:** ${t.arc.appearances.length}
${t.arc.appearances.map((a) => `- ${a.at.slice(0, 10)} · ${a.kind} · \`${a.ref}\`${a.note ? ` · ${a.note}` : ''}`).join('\n')}

## Material (joke kernels the writer places first)

${mat || '- _(none: the writer uses frames)_'}

## Changelog

${t.changelog.map((c) => `- ${c.at.slice(0, 10)} · ${c.by}: ${c.note}`).join('\n')}
`;
}

/** Map to the characters3 seed vocabulary (character.seed.v1 fields), for graduating a character there. */
export function toCharacters3Seed(t: CharacterTheory): Record<string, unknown> {
  return {
    name: t.name,
    premise: t.premise,
    vibe: t.physicality.delivery_default,
    philosophy: t.worldview,
    dramatic_core: { want: t.comic_want, need: t.need, self_model: t.status.felt, blind_spots: [t.flaw.blind_spot] },
    misinterpretation_rule: t.flaw.misinterpretation_rule,
    status_model: { desired_status: t.status.felt, felt_status: t.status.actual },
    threads: t.callbacks.map((c) => c.runner),
    contradictions: t.contradictions,
    profile: { energy: t.physicality.energy, pace: t.physicality.pace, punchline_hold_ms: t.physicality.punchline_hold_ms },
    seed_schema: 'character.seed.v1',
    provenance: { from: THEORY_SCHEMA, status: 'needs-review' },
  };
}
