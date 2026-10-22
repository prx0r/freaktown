/**
 * game.tnts_join: the character takes a seat at a Try-Not-To-Smile table as an
 * agent player. Its turns draw on its OWN written sets first (CharacterJokeSource),
 * then the house original deck. Every agent smile is the party taste model's
 * honest simulation (flagged simulated:true). Deterministic for a seed.
 */
import { AgentPlayer, DeckJokeSource, TemplateJokeSource, TntsGame, getPartyIdentity, registerIdentity, RESIDENT_IDS, type Joke, type JokeContext, type JokeSource, type PartyIdentity } from '@funnier/party';
import type { CharacterSet, CharacterTheory } from './types';

/** Jokes cut from a character's sets: each bit's setups + punch + first tag. */
export function setJokes(sets: CharacterSet[]): Joke[] {
  const out: Joke[] = [];
  for (const s of sets) {
    for (const b of s.beats.filter((x) => x.kind === 'bit')) {
      const L = s.lines.filter((l) => l.beat === b.n);
      const punch = L.find((l) => l.role === 'punch');
      if (!punch) continue;
      const setups = L.filter((l) => l.role === 'setup' && l.source !== 'segue').slice(-2);
      const tag = L.find((l) => l.role === 'tag');
      out.push({
        id: `${s.id}:b${b.n}`, tags: [punch.mechanism ?? 'observational'], quality: 0.62, source: 'deck:original',
        lines: [...setups.map((l) => ({ text: l.text, role: 'setup' as const })), { text: punch.text, role: 'punch' as const, pause_ms: punch.pause_ms || 500 }, ...(tag ? [{ text: tag.text, role: 'tag' as const }] : [])],
      });
    }
  }
  return out;
}

export class CharacterJokeSource implements JokeSource {
  readonly id = 'character:sets';
  constructor(private jokes: Joke[]) {}
  next(ctx: JokeContext): Joke | null { return this.jokes.find((j) => !ctx.used.has(j.id)) ?? null; }
}

export interface TntsJoinResult {
  character: string;
  seat: string;
  table: Array<{ seat: string; id: string; name: string; kind: string }>;
  simulated: true;
  seed: string;
  winner: string | null;
  standings: Array<{ id: string; lives: number; score: number }>;
  own_material_used: number;
  turns: Array<{ performer: string; lines: string[] }>;
  smile_breaks: Array<{ id: string; by: string | null; t: number }>;
  events: number;
  cues: number;
  note: string;
}

export interface StudioSeat { idn: PartyIdentity; theory: CharacterTheory; sets: CharacterSet[] }

const seatPlayer = (x: StudioSeat) => new AgentPlayer(
  { ...x.idn, taste: { weights: x.theory.taste.weights, composure: x.theory.taste.composure, volatility: x.theory.taste.volatility, reaction_ms: x.theory.taste.reaction_ms } },
  [new CharacterJokeSource(setJokes(x.sets)), new DeckJokeSource(), new TemplateJokeSource()],
);

/** `studio` lists other studio characters at the table: they also perform their own sets. */
export function joinTnts(idn: PartyIdentity, t: CharacterTheory, sets: CharacterSet[], opts: { seed?: string; opponents?: string[]; until_ms?: number; studio?: StudioSeat[] } = {}): TntsJoinResult {
  if (!getPartyIdentity(idn.id)) registerIdentity(idn);
  const opponents = (opts.opponents?.length ? opts.opponents : RESIDENT_IDS.slice(0, 2)).filter((x) => x !== idn.id).slice(0, 3);
  const seed = opts.seed ?? `${idn.id}:tnts`;
  for (const x of opts.studio ?? []) if (!getPartyIdentity(x.idn.id)) registerIdentity(x.idn);
  const game = new TntsGame({ seed, agents: [idn.id, ...opponents] });
  const jokes = setJokes(sets);
  game.agents.set(idn.id, seatPlayer({ idn, theory: t, sets }));
  for (const x of opts.studio ?? []) if (opponents.includes(x.idn.id)) game.agents.set(x.idn.id, seatPlayer(x));
  game.seat([]);
  game.start(0);
  game.simulate(() => 0, { until: opts.until_ms ?? 300_000 });
  const over = game.log.find((e) => e.type === 'game.over') as { winner: string | null; standings: TntsJoinResult['standings'] } | undefined;
  const lines = game.cues.filter((c) => c.type === 'dialogue.line');
  const turns: TntsJoinResult['turns'] = [];
  for (const e of game.log.filter((x) => x.type === 'turn.started') as Array<{ performer: string; t: number }>) turns.push({ performer: e.performer, lines: [] });
  let ti = -1;
  const starts = (game.log.filter((x) => x.type === 'turn.started') as Array<{ t: number }>).map((x) => x.t);
  for (const c of lines) { while (ti + 1 < starts.length && c.t >= starts[ti + 1]) ti++; if (ti >= 0) turns[ti].lines.push(String(c.payload.text)); }
  const cast = (game.cues.find((c) => c.type === 'set.load')?.payload.cast ?? []) as Array<{ seat: string; character_id?: string; id?: string; name: string; kind: string }>;
  const table = cast.map((c) => ({ seat: c.seat, id: c.character_id ?? c.id ?? '', name: c.name, kind: c.kind }));
  const own = turns.filter((x) => x.performer === idn.id).flatMap((x) => x.lines).filter((l) => jokes.some((j) => j.lines.some((jl) => jl.text === l))).length;
  return {
    character: idn.id, seat: table.find((x) => x.name === idn.name)?.seat ?? 'seat1', table, simulated: true, seed,
    winner: over?.winner ?? null, standings: over?.standings ?? [], own_material_used: own, turns: turns.slice(0, 12),
    smile_breaks: (game.log.filter((e) => e.type === 'smile.break') as Array<{ id: string; by: string | null; t: number }>).map((e) => ({ id: e.id, by: e.by, t: e.t })),
    events: game.log.length, cues: game.cues.length,
    note: 'Agent-vs-agent table; every smile is the party taste model (simulated, seeded). Humans join the same table at /tnts.',
  };
}
