/**
 * character.create: a premise (or "let the agent choose") → a party identity
 * (via @funnier/party createIdentity, so the GLB recipe and taste model are the
 * same ones every room uses) + a full theory. Deterministic for a seed.
 */
import { createIdentity, mulberry32, pick, type Delivery, type IdentityBrief, type Mechanism, type PartyIdentity, type Rng } from '@funnier/party';
import { FIRST_NAMES, FLAWS, OCCUPATIONS, SAFETY_RAILS, WANTS, type FlawSeed, type OccupationSeed } from './banks';
import { THEORY_SCHEMA, type CharacterTheory, type MaterialKernel } from './types';

export interface CreateBrief {
  /** Who is creating (the agent's id, e.g. "hark"). */
  by: string;
  /** A premise in plain words ("a ghost who works as an estate agent and is too honest"). Omit and set choose=true to let the agent choose. */
  premise?: string;
  choose?: boolean;
  seed?: string;
  name?: string;
  bio?: string;
  catchphrase?: string;
  delivery?: Delivery;
  writes?: Mechanism[];
  head?: IdentityBrief['head'];
  voice_id?: string;
}

const AXIOLOGY: Record<string, string> = {
  vanity: 'Being noticed is the highest good.', perfectionism: 'Getting it exactly right matters more than getting it done.',
  cowardice: 'Safety first, second and third.', pedantry: 'Accuracy is a form of kindness.', neediness: 'Company is everything; leaving is cruelty.',
  literalism: 'Instructions are sacred.', overconfidence: 'Nerve is the only virtue.', martyrdom: 'A sacrifice only counts if somebody saw it.',
};
const FLAW_HINTS: Record<string, string[]> = {
  vanity: ['vain', 'diva', 'show-off', 'famous'], perfectionism: ['perfectionist', 'perfect', 'fussy'], cowardice: ['coward', 'scared', 'nervous', 'anxious'],
  pedantry: ['pedant', 'pedantic', 'correct', 'know-it-all'], neediness: ['needy', 'clingy', 'lonely'], literalism: ['literal', 'robot', 'rules'],
  overconfidence: ['overconfident', 'cocky', 'arrogant', 'reckless'], martyrdom: ['martyr', 'selfless', 'helpful', 'servant'],
};
const REGISTER: Record<Delivery, { register: string; shape: string; max: number; contractions: CharacterTheory['voice']['contractions'] }> = {
  deadpan: { register: 'flat, formal, economical', shape: 'short flat statements; the punch is the shortest sentence', max: 20, contractions: 'sparingly' },
  deliberate: { register: 'measured and precise, slightly official', shape: 'complete sentences, lists of three', max: 22, contractions: 'sparingly' },
  manic: { register: 'fast, breathless, interrupting itself', shape: 'run-ons and fragments, restarts mid-sentence', max: 28, contractions: 'freely' },
  warm: { register: 'friendly, plain, a bit proud', shape: 'conversational sentences that end on the image', max: 22, contractions: 'freely' },
  conspiratorial: { register: 'hushed, confiding, salesy', shape: 'asides and reveals; the punch is a whisper', max: 22, contractions: 'freely' },
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const slugKey = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/** "a ghost who works as an estate agent" → { who, does }. */
export function parseCharacterPremise(premise: string): { who: string; does: string | null } {
  const p = premise.trim().replace(/[.!]+$/, '');
  const m = p.match(/^(.+?)\s+(?:who|that|which)\s+(.+)$/i);
  return m ? { who: m[1], does: m[2] } : { who: p, does: null };
}

function matchOccupation(premise: string): OccupationSeed | undefined {
  const words = premise.toLowerCase();
  return OCCUPATIONS.find((o) => [o.key.replace('-', ' '), ...o.job.toLowerCase().split(/\W+/).filter((w) => w.length > 5)].some((k) => words.includes(k)));
}

function matchFlaw(premise: string, rng: Rng): FlawSeed {
  const words = premise.toLowerCase();
  return FLAWS.find((f) => FLAW_HINTS[f.key]?.some((h) => words.includes(h))) ?? pick(rng, FLAWS);
}

function genericOccupation(premise: string, rng: Rng): OccupationSeed {
  const { who, does } = parseCharacterPremise(premise);
  const noun = cap(who.replace(/^(a|an|the)\s+/i, '').split(/\s+/).slice(-1)[0] ?? 'Comic');
  const delivery = pick(rng, ['deadpan', 'deliberate', 'warm', 'conspiratorial', 'manic'] as const);
  return {
    key: slugKey(noun), noun, job: who.replace(/^(a|an|the)\s+/i, (m) => m.toLowerCase()), job_short: who.replace(/^(a|an|the)\s+/i, ''),
    props: ['the job', 'the rules', 'the queue'], unusual: does ?? `is ${who} and treats it as a calling`, base_reality: `an ordinary day in the life of ${who}`,
    attitude: [pick(rng, ['weird', 'hard', 'stupid', 'scary'] as const)], tic: 'Anyway.', catchphrase: 'That is the job. Goodnight.',
    head: pick(rng, ['sphere', 'box', 'blob'] as const), delivery, writes: [pick(rng, ['observational', 'absurd', 'deadpan'] as const), 'self-deprecating'],
    lens: `everything is about being ${who}`, anchors: [`has been ${who} for longer than anyone asked`], kernels: [],
  };
}

const fill = (s: string, o: OccupationSeed, name: string) => s.replace(/\{name\}/g, name).replace(/\{job\}/g, o.job_short).replace(/\{prop\}/g, o.props[0]).replace(/\{prop2\}/g, o.props[1]).replace(/\{prop3\}/g, o.props[2]);

/** The deterministic creation flow. Returns the identity record and its theory. */
export function createCharacter(brief: CreateBrief, at: string): { identity: PartyIdentity; theory: CharacterTheory } {
  const seed = brief.seed ?? `${brief.by}:${brief.premise ?? 'agent-choice'}:${brief.name ?? ''}`;
  const rng = mulberry32(`characters:${seed}`);
  const choose = brief.choose || !brief.premise;
  const occ = choose ? pick(rng, OCCUPATIONS) : matchOccupation(brief.premise!) ?? genericOccupation(brief.premise!, rng);
  const flaw = choose ? pick(rng, FLAWS) : matchFlaw(brief.premise!, rng);
  const want = pick(rng, WANTS);
  const name = brief.name ?? `${pick(rng, FIRST_NAMES)} ${occ.noun}`;
  const delivery = brief.delivery ?? occ.delivery;
  const writes = brief.writes?.length ? brief.writes : occ.writes;
  const catchphrase = brief.catchphrase ?? occ.catchphrase;
  const premise = choose ? `${cap(occ.job)}; ${occ.unusual}` : brief.premise!.trim();
  const logline = brief.bio ?? `${name}: ${occ.job}. ${name.split(' ')[0]} ${occ.unusual}, and ${flaw.flaw.split(':')[0]} keeps making it worse.`;
  const identity = createIdentity({ by: brief.by, seed, name, bio: logline, writes, delivery, catchphrase, head: brief.head ?? occ.head, voice: brief.voice_id ? { engine: 'edge', id: brief.voice_id } : undefined });
  const reg = REGISTER[delivery];
  const material: MaterialKernel[] = [
    ...occ.kernels.map((k, i) => ({ ...k, id: `${occ.key}-${i + 1}`, setups: k.setups.map((s) => fill(s, occ, name)) })),
    { ...flaw.kernel, id: `${flaw.key}-1` },
  ];
  const theory: CharacterTheory = {
    schema: THEORY_SCHEMA, id: identity.id, name, logline, premise, intro: choose || matchOccupation(brief.premise ?? '') ? occ.job : undefined, origin: choose ? 'agent-choice' : 'premise',
    comic_want: want, need: flaw.need,
    flaw: { flaw: flaw.flaw, blind_spot: flaw.blind_spot, misinterpretation_rule: flaw.rule, misreads: flaw.misreads },
    status: { plays: flaw.status.plays, to_audience: flaw.status.plays === 'high' ? 'low' : 'high', felt: flaw.status.felt, actual: flaw.status.actual, see_saw: flaw.status.see_saw },
    point_of_view: { attitude: occ.attitude, take: `${cap(occ.lens)}.`, lens: occ.lens },
    game: {
      base_reality: occ.base_reality, unusual_thing: `${name} ${occ.unusual}.`, pattern: `${cap(occ.unusual)}; every time, ${flaw.rule.replace(/^treats/, 'treating')} makes it worse.`,
      heighten: [`If ${name} ${occ.unusual}, then it happens at the worst possible moment.`, `If ${name} ${flaw.rule}, then the bigger the ${flaw.misreads[0].trigger}, the bigger the misreading.`, `If it works once, ${name} makes it policy.`],
      explore: [`Why? Because ${occ.anchors[0]}.`, `Why? Because underneath it all, ${name} wants ${want}.`],
    },
    voice: { register: reg.register, sentence_shape: reg.shape, max_sentence_words: reg.max, contractions: reg.contractions, exclamations: delivery === 'manic', verbal_tics: [occ.tic], signature_words: occ.props.map((p) => p.replace(/^the /, '')), forbidden_words: ['lol', 'literally', 'awesome', 'vibes'], substitutions: {} },
    physicality: { delivery_default: delivery, energy: delivery === 'manic' ? 0.85 : delivery === 'deadpan' ? 0.3 : 0.55, pace: delivery === 'manic' ? 1.2 : delivery === 'deliberate' ? 0.9 : 1, punchline_hold_ms: delivery === 'deadpan' ? 1300 : delivery === 'manic' ? 700 : 1000, stillness: delivery === 'manic' ? 'never still; moves on every setup' : 'still on the punch, moves only on the tag', gestures: [`gestures at ${occ.props[0]}`, 'small shrug on the tag'] },
    taste: { ...identity.taste, smiles_at: [flaw.smiles_at, `jokes about ${occ.props[0]}`], stone_face_at: [flaw.stone_face_at] },
    writes,
    worldview: { ontology: `The world works like this: ${occ.lens}.`, epistemology: `If it happened near ${occ.props[0]}, it is true.`, axiology: AXIOLOGY[flaw.key] ?? 'Doing the job is the highest good.', causality: `Problems happen because people ignore ${occ.props[0]}.`, agency: `With ${occ.props[1]}, ${name} can change anything except ${name}.` },
    contradictions: [flaw.contradiction, `${cap(occ.job_short)} by trade, comedian by accident`],
    backstory_anchors: occ.anchors,
    catchphrases: [catchphrase, occ.tic],
    callbacks: occ.kernels.filter((k) => k.callback).map((k, i) => ({ id: `${occ.key}-runner-${i + 1}`, runner: k.topic, seed_line: k.callback! })),
    taboo: { never_targets: ['protected groups', 'real private people', 'the audience\'s bodies'], never_topics: ['self-harm', 'sexual content', 'real tragedies'], never_says: [], safety_rails: SAFETY_RAILS },
    relationships: [{ who: 'The audience', dynamic: flaw.status.plays === 'high' ? 'performs for them, expects tribute' : 'confides in them, hopes for backup', metaphor: flaw.status.plays === 'high' ? 'a monarch and a crowd that has not bowed yet' : 'a witness and the only jury that might acquit', status: flaw.status.plays === 'high' ? 'above' : 'below' }],
    humanity: `Underneath ${flaw.flaw.split(':')[0]}, ${name} just wants ${want}, and keeps showing up.`,
    arc: {
      shape: 'circular',
      stages: [
        { n: 1, title: 'Introduction', shift: 'the status quo and the game, shown plainly', status: 'current' },
        { n: 2, title: 'The runner', shift: 'a callback becomes a running gag the audience expects', status: 'planned' },
        { n: 3, title: 'The crack', shift: `the blind spot is nearly seen: ${flaw.blind_spot}`, status: 'planned' },
        { n: 4, title: 'The near miss', shift: `${name} almost gets ${want}; the flaw ruins it`, status: 'planned' },
        { n: 5, title: 'Reset', shift: 'back to the status quo, one relationship slightly deeper', status: 'planned' },
      ],
      reset_rule: 'Whatever is learned is forgotten by the next set; the flaw survives, the relationships deepen.',
      appearances: [],
    },
    material,
    props: occ.props,
    changelog: [{ at, by: brief.by, note: choose ? `created by agent choice (seed "${seed}")` : `created from premise "${premise}" (seed "${seed}")` }],
  };
  return { identity, theory };
}

/** A theory scaffold for an identity that already exists (character.create adopt). */
export function theoryFromIdentity(idn: PartyIdentity, by: string, at: string): CharacterTheory {
  const { theory } = createCharacter({ by, premise: idn.persona.bio, name: idn.name, seed: `adopt:${idn.id}`, delivery: idn.persona.delivery, writes: idn.persona.writes, catchphrase: idn.persona.catchphrase, bio: idn.persona.bio }, at);
  return {
    ...theory, id: idn.id, origin: 'adopted', logline: idn.persona.bio,
    taste: { ...idn.taste, smiles_at: theory.taste.smiles_at, stone_face_at: theory.taste.stone_face_at },
    catchphrases: idn.persona.catchphrase ? [idn.persona.catchphrase] : theory.catchphrases,
    changelog: [{ at, by, note: `adopted existing identity ${idn.id}` }],
  };
}
