/**
 * Joke sources. ORIGINAL material only:
 *   - ORIGINAL_DECK: one-liners and short bits written for FUNNIER (no
 *     third-party jokes, no corpus lines). License: same as this repo.
 *   - TemplateJokeSource: combinatorial original templates (setup frame ×
 *     subject × twist) so agents don't run out mid-game.
 *   - LlmJokeSource: the hook for a model later. It is OFF unless a caller
 *     injects `complete()`; nothing here makes a network call or spends money.
 *
 * The party decks in party.py are prompts for humans, not agent material, so
 * they are not drawn from here.
 */
import { pick, type Rng } from './rng';

export type Mechanism = 'wordplay' | 'absurd' | 'observational' | 'deadpan' | 'misdirection' | 'self-deprecating' | 'meta' | 'callback';
export const MECHANISMS: readonly Mechanism[] = ['wordplay', 'absurd', 'observational', 'deadpan', 'misdirection', 'self-deprecating', 'meta', 'callback'];

export type Delivery = 'deadpan' | 'deliberate' | 'manic' | 'warm' | 'conspiratorial';
export const DELIVERIES: readonly Delivery[] = ['deadpan', 'deliberate', 'manic', 'warm', 'conspiratorial'];

export interface JokeLine { text: string; role: 'setup' | 'punch' | 'tag'; delivery?: Delivery; pause_ms?: number }
export interface Joke {
  id: string;
  lines: JokeLine[];
  tags: Mechanism[];
  /** Writer's own estimate 0..1 (the taste model does the real judging). */
  quality: number;
  source: 'deck:original' | 'template:original' | 'llm';
}

const J = (id: string, setup: string, punch: string, tags: Mechanism[], quality: number, tag?: string): Joke => ({
  id, tags, quality, source: 'deck:original',
  lines: [{ text: setup, role: 'setup' }, { text: punch, role: 'punch', pause_ms: 450 }, ...(tag ? [{ text: tag, role: 'tag' as const }] : [])],
});

export const ORIGINAL_DECK: readonly Joke[] = [
  J('o01', 'My smart fridge started recommending recipes.', 'Mostly it recommends I close the door.', ['observational', 'deadpan'], 0.55),
  J('o02', 'I joined a support group for procrastinators.', 'We meet next week. Probably.', ['self-deprecating', 'misdirection'], 0.5),
  J('o03', 'My calendar has a color for every kind of meeting.', 'Grey means it could have been a nap.', ['observational'], 0.55),
  J('o04', 'I bought a self-help book called "Stop Overthinking".', 'I have read the title four hundred times. What did they mean by it?', ['self-deprecating', 'absurd'], 0.6),
  J('o05', 'The weather app says ten percent chance of rain.', 'I have never felt so personally targeted by a decimal.', ['observational', 'absurd'], 0.6),
  J('o06', 'My houseplant is thriving.', 'It is plastic. I am still proud of us.', ['deadpan', 'misdirection'], 0.6),
  J('o07', 'I asked the hotel for a room with a view.', 'They gave me a mirror and said, "You are the view."', ['absurd', 'misdirection'], 0.55),
  J('o08', 'I tried a standing desk.', 'Now I just sit near it, with respect.', ['self-deprecating', 'deadpan'], 0.55),
  J('o09', 'My phone says my screen time is up twelve percent.', 'Up from what? It has been watching me the whole time.', ['observational', 'meta'], 0.5),
  J('o10', 'I am learning to juggle.', 'So far I can drop three things at once.', ['wordplay', 'self-deprecating'], 0.6),
  J('o11', 'A pigeon walked into the cafe today.', 'Ordered nothing, judged everyone. Honestly, a regular.', ['absurd', 'observational'], 0.6),
  J('o12', 'I labelled every box when I moved house.', 'They all say "misc". I am a man of mystery to myself.', ['self-deprecating', 'observational'], 0.55),
  J('o13', 'They say laughter is the best medicine.', 'Which explains why this room has such terrible insurance.', ['meta', 'misdirection'], 0.5),
  J('o14', 'My GPS said "recalculating" four times in a row.', 'Same, GPS. Same.', ['observational', 'self-deprecating'], 0.55),
  J('o15', 'I was going to tell a joke about time travel.', 'But you hated it.', ['wordplay', 'misdirection'], 0.65),
  J('o16', 'I put my socks on a hot wash to shrink them.', 'Now they fit my old self-esteem.', ['absurd', 'self-deprecating'], 0.5),
  J('o17', 'My cat knocked a glass off the table and looked right at me.', 'That is not an accident. That is a performance review.', ['observational', 'absurd'], 0.6),
  J('o18', 'I started a band called "Silent Partner".', 'We have never played a note. Critics call it our best work.', ['deadpan', 'absurd'], 0.6),
  J('o19', 'The toaster has one setting.', 'Destiny.', ['deadpan', 'absurd'], 0.6),
  J('o20', 'I am not saying the meeting ran long.', 'But we elected a new chairperson for the second half.', ['observational', 'absurd'], 0.6),
  J('o21', 'I tried meditating.', 'Ten minutes in, my brain started a podcast.', ['observational', 'self-deprecating'], 0.55),
  J('o22', 'Our office plant got promoted.', 'Fair. It does not interrupt, and it grows.', ['absurd', 'deadpan'], 0.55),
  J('o23', 'I keep a diary of all my bad ideas.', 'It is in a lovely leather binding. That was the first one.', ['misdirection', 'self-deprecating'], 0.6),
  J('o24', 'I got a fitness tracker.', 'It mostly tracks how long I look at the fitness tracker.', ['observational', 'meta'], 0.55),
  J('o25', 'Scientists say we only use ten percent of our brains.', 'I am using mine to remember a jingle from 2009.', ['self-deprecating', 'misdirection'], 0.5),
  J('o26', 'The sign said "wet paint".', 'So I trusted it. That is the kind of person I am.', ['deadpan', 'self-deprecating'], 0.5),
  J('o27', 'I bought a ladder for my career.', 'Turns out it was a step stool, and the career was a shelf.', ['wordplay', 'absurd'], 0.55),
  J('o28', 'My neighbour mows his lawn at seven every Sunday.', 'He calls it gardening. I call it a drum solo.', ['observational'], 0.5),
  J('o29', 'I have a photographic memory.', 'It just never developed.', ['wordplay'], 0.6),
  J('o30', 'I am trying not to smile right now.', 'Which is the most relatable thing anyone at this table will say tonight.', ['meta', 'callback'], 0.5),
  J('o31', 'A spoon and a fork had an argument.', 'The knife just stayed out of it. Sharp guy.', ['wordplay', 'absurd'], 0.55),
  J('o32', 'I read that octopuses have three hearts.', 'Three hearts, and not one of them texts back.', ['absurd', 'misdirection'], 0.6),
];

/** Original combinatorial templates: frame + subject + twist. */
const FRAMES: ReadonlyArray<{ setup: (x: string) => string; punch: (x: string, y: string) => string; tags: Mechanism[] }> = [
  { setup: (x) => `I tried to explain ${x} to my grandmother.`, punch: (_x, y) => `She said, "So it's ${y}," and honestly, she's right.`, tags: ['observational', 'misdirection'] },
  { setup: (x) => `They invented ${x} to save us time.`, punch: (_x, y) => `I now spend that time on ${y}.`, tags: ['observational', 'deadpan'] },
  { setup: (x) => `My therapist asked me to describe ${x} in one word.`, punch: (_x, y) => `I said "${y}", and she billed me for two.`, tags: ['absurd', 'self-deprecating'] },
  { setup: (x) => `There is a support group for people addicted to ${x}.`, punch: (_x, y) => `It is held inside ${y}. Nobody has noticed.`, tags: ['absurd', 'misdirection'] },
];
const SUBJECTS = ['the group chat', 'cloud storage', 'smart speakers', 'loyalty cards', 'self-checkout', 'password rules', 'the office printer', 'reply-all'];
const TWISTS = ['a haunted filing cabinet', 'a very polite trap', 'a raffle nobody entered', 'homework for adults', 'a shrug with a logo', 'a queue with Wi-Fi', 'a ghost that bills hourly', 'a hobby that hates you'];

export interface JokeContext { rng: Rng; used: Set<string>; prefer?: Mechanism[]; performerId?: string }
export interface JokeSource { readonly id: string; next(ctx: JokeContext): Joke | null }

export class DeckJokeSource implements JokeSource {
  readonly id = 'deck:original';
  constructor(private deck: readonly Joke[] = ORIGINAL_DECK) {}
  next(ctx: JokeContext): Joke | null {
    const fresh = this.deck.filter((j) => !ctx.used.has(j.id));
    if (!fresh.length) return null;
    const pref = ctx.prefer ?? [];
    const scored = fresh.map((j) => ({ j, w: 1 + 2 * j.tags.filter((t) => pref.includes(t)).length + ctx.rng() }));
    scored.sort((a, b) => b.w - a.w);
    return scored[0].j;
  }
}

export class TemplateJokeSource implements JokeSource {
  readonly id = 'template:original';
  next(ctx: JokeContext): Joke | null {
    for (let tries = 0; tries < 20; tries++) {
      const fi = Math.floor(ctx.rng() * FRAMES.length);
      const x = pick(ctx.rng, SUBJECTS);
      const y = pick(ctx.rng, TWISTS);
      const id = `t${fi}-${SUBJECTS.indexOf(x)}-${TWISTS.indexOf(y)}`;
      if (ctx.used.has(id)) continue;
      const f = FRAMES[fi];
      return { id, tags: f.tags, quality: 0.45, source: 'template:original', lines: [{ text: f.setup(x), role: 'setup' }, { text: f.punch(x, y), role: 'punch', pause_ms: 450 }] };
    }
    return null;
  }
}

/**
 * LLM hook — disabled by default. Inject `complete` (e.g. a local model, or a
 * metered API once spend is approved) to turn it on. Output is parsed as
 * "setup || punch" and tagged by the caller's preferred mechanism.
 */
export class LlmJokeSource implements JokeSource {
  readonly id = 'llm';
  constructor(private complete?: (prompt: string) => string | null) {}
  get enabled(): boolean { return typeof this.complete === 'function'; }
  next(ctx: JokeContext): Joke | null {
    if (!this.complete) return null;
    const mech = ctx.prefer?.[0] ?? 'observational';
    const out = this.complete(`Write one ORIGINAL clean ${mech} joke as "setup || punch". No existing jokes.`);
    if (!out || !out.includes('||')) return null;
    const [setup, punch] = out.split('||').map((x) => x.trim());
    const id = `llm-${ctx.used.size}`;
    return { id, tags: [mech], quality: 0.5, source: 'llm', lines: [{ text: setup, role: 'setup' }, { text: punch, role: 'punch', pause_ms: 450 }] };
  }
}

/** Try sources in order; marks the joke used. */
export function nextJoke(sources: JokeSource[], ctx: JokeContext): Joke {
  for (const s of sources) {
    const j = s.next(ctx);
    if (j) { ctx.used.add(j.id); return j; }
  }
  // last resort: never stall a turn
  const j: Joke = { id: `fallback-${ctx.used.size}`, tags: ['meta'], quality: 0.3, source: 'template:original', lines: [{ text: 'I had a joke for this moment.', role: 'setup' }, { text: 'It is still loading. Like me.', role: 'punch', pause_ms: 400 }] };
  ctx.used.add(j.id);
  return j;
}
