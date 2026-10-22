import { describe, expect, it } from 'vitest';
import { TntsGame } from '../src/game';
import { reactToJoke, rateJoke, curveAt } from '../src/taste';
import { ORIGINAL_DECK, DeckJokeSource, TemplateJokeSource, LlmJokeSource, nextJoke } from '../src/jokes';
import { createIdentity, getPartyIdentity, registerIdentity, RESIDENT_IDS, validateIdentity } from '../src/identity';
import { mulberry32 } from '../src/rng';

const AGENTS = ['pog.doug-deadline', 'pog.madame-chrysalis', 'pog.the-algorithm'];

function table(seed = 'demo') {
  const g = new TntsGame({ seed, agents: AGENTS });
  g.seat([{ id: 'you', name: 'You' }]);
  g.calibrated('you', 0.05, false, 0);
  g.start(0);
  return g;
}

describe('TntsGame: human vs agents', () => {
  it('seats agents with persistent identities and casts the set', () => {
    const g = table();
    expect(g.cues[0]).toMatchObject({ type: 'set.load', payload: { setId: 'podcast' } });
    const cast = g.cues[0].payload.cast as Array<{ seat: string; name: string; kind: string }>;
    expect(cast.map((c) => c.seat)).toEqual(['seat1', 'seat2', 'seat3', 'seat4']);
    expect(cast[0].name).toBe('Doug Deadline');
    expect(cast[3]).toMatchObject({ name: 'You', kind: 'human' });
  });

  it('a stone-faced human survives; a smiling human is eliminated', () => {
    const stone = table('s1');
    stone.simulate(() => 0.08, { until: 400_000 });
    expect(stone.state.players.you.out).toBe(false);
    expect(stone.state.phase).toBe('over');

    const smiler = table('s1');
    // grins 0.9 from 1.2 s to 2.4 s after every agent punchline
    smiler.simulate((_id, t) => {
      const p = smiler.state.performer;
      return p && p !== 'you' && (t - smiler.state.turnStartedAt) % 6000 > 1200 && (t - smiler.state.turnStartedAt) % 6000 < 2400 ? 0.9 : 0.05;
    }, { until: 400_000 });
    expect(smiler.state.players.you.out).toBe(true);
    const outEv = smiler.log.find((e) => e.type === 'player.out' && e.id === 'you');
    expect(outEv).toBeTruthy();
    expect(smiler.log.filter((e) => e.type === 'smile.break' && e.id === 'you')).toHaveLength(3);
  });

  it('agents deliver lines through the stage and show (simulated) smiles on their face', () => {
    const g = table('cues');
    g.simulate(() => 0.05, { until: 120_000 });
    const lines = g.cues.filter((c) => c.type === 'dialogue.line');
    expect(lines.length).toBeGreaterThan(2);
    expect(lines[0].payload).toHaveProperty('seat');
    const faces = g.cues.filter((c) => c.type === 'face.expression');
    expect(faces.length).toBeGreaterThan(0);
    const agentBreaks = g.log.filter((e) => e.type === 'smile.break' && e.id !== 'you');
    for (const b of agentBreaks) expect(b).toMatchObject({ simulated: true });
  });

  it('is deterministic for a seed', () => {
    const run = () => { const g = table('det'); g.simulate(() => 0.05, { until: 200_000 }); return JSON.stringify(g.log); };
    expect(run()).toBe(run());
  });
});

describe('taste model (honest, simulated smile)', () => {
  it('rating follows taste; crack probability follows rating vs composure', () => {
    const pun = ORIGINAL_DECK.find((j) => j.id === 'o29')!; // wordplay
    const lover = { weights: { wordplay: 1 }, composure: 0.4, volatility: 0, reaction_ms: 300 };
    const hater = { weights: { wordplay: -1 }, composure: 0.8, volatility: 0, reaction_ms: 300 };
    const a = rateJoke(lover, pun, mulberry32(1));
    const b = rateJoke(hater, pun, mulberry32(1));
    expect(a.rating).toBeGreaterThan(b.rating);
    expect(a.pCrack).toBeGreaterThan(0.5);
    expect(b.pCrack).toBeLessThan(0.01);
  });

  it('a crack curve crosses 0.5 for longer than the hold; a twitch never does', () => {
    const j = ORIGINAL_DECK[0];
    const crack = reactToJoke({ weights: { observational: 1, deadpan: 1 }, composure: 0, volatility: 0, reaction_ms: 300 }, j, mulberry32(3));
    expect(crack.cracked).toBe(true);
    let above = 0;
    for (let t = 0; t < 4000; t += 10) if (curveAt(crack, t) > 0.5) above += 10;
    expect(above).toBeGreaterThan(400);
    const twitch = reactToJoke({ weights: {}, composure: 1, volatility: 0, reaction_ms: 300 }, j, mulberry32(3));
    expect(twitch.cracked).toBe(false);
    for (let t = 0; t < 4000; t += 10) expect(curveAt(twitch, t)).toBeLessThan(0.5);
  });
});

describe('joke sources (original only; LLM hook off by default)', () => {
  it('deck prefers the performer mechanisms and never repeats', () => {
    const used = new Set<string>();
    const ids = new Set<string>();
    const rng = mulberry32(7);
    for (let i = 0; i < 40; i++) ids.add(nextJoke([new DeckJokeSource(), new TemplateJokeSource()], { rng, used, prefer: ['wordplay'] }).id);
    expect(ids.size).toBe(40);
    const first = new DeckJokeSource().next({ rng: mulberry32(1), used: new Set(), prefer: ['wordplay'] })!;
    expect(first.tags).toContain('wordplay');
    expect(ORIGINAL_DECK.every((j) => j.source === 'deck:original')).toBe(true);
  });
  it('LLM source is disabled unless a completer is injected', () => {
    expect(new LlmJokeSource().enabled).toBe(false);
    expect(new LlmJokeSource().next({ rng: mulberry32(1), used: new Set() })).toBeNull();
    const j = new LlmJokeSource(() => 'A setup || a punch').next({ rng: mulberry32(1), used: new Set() });
    expect(j?.lines.map((l) => l.text)).toEqual(['A setup', 'a punch']);
  });
});

describe('identities', () => {
  it('residents are pog.* cast identities with a party profile', () => {
    for (const id of RESIDENT_IDS) expect(getPartyIdentity(id)?.taste).toBeTruthy();
    expect(getPartyIdentity('pog.doug-deadline')?.name).toBe('Doug Deadline');
  });
  it('an agent can create + register its own identity (seeded, valid, persistent in-process)', () => {
    const a = createIdentity({ by: 'agent.test', seed: 'x1' });
    const b = createIdentity({ by: 'agent.test', seed: 'x1' });
    expect(a).toEqual(b);
    expect(validateIdentity(a)).toEqual([]);
    registerIdentity(a);
    expect(getPartyIdentity(a.id)?.name).toBe(a.name);
    const g = new TntsGame({ agents: [a.id, 'pog.doug-deadline'] });
    g.seat([{ id: 'you', name: 'You' }]);
    expect((g.cues[0].payload.cast as Array<{ avatar_url: string }>)[0].avatar_url).toBe(`identities/${a.id}.glb`);
  });
});
