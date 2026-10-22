/**
 * Party identities — persistent agent characters that sit in game seats.
 *
 * No parallel cast: residents are the repo's `pog.*` identities
 * (@funnier/sketch registry: name, family, voice, motion traits) with a party
 * profile layered on top (comedic persona + taste model). Agent-made
 * identities (P3) are full records created through `createIdentity()` and
 * registered in identities/registry.json (CLI) or at runtime (`register`),
 * so the same character turns up in every room it joins.
 */
import { getIdentity } from '@funnier/sketch';
import registryJson from '../identities/registry.json';
import { hashString, mulberry32, pick, round3, type Rng } from './rng';
import { MECHANISMS, type Delivery, type Mechanism } from './jokes';
import { randomTaste, type TasteModel } from './taste';

export interface PartyPersona {
  /** One line: who they are on stage. */
  bio: string;
  /** Mechanisms they write in (their jokes lean this way). */
  writes: Mechanism[];
  /** Their default delivery. */
  delivery: Delivery;
  /** Optional verbal tic used as a tag. */
  catchphrase?: string;
}

export interface PartyVoice {
  /** "edge" voice id (only a NAME: no TTS is called in this package), or "gibberish". */
  engine: 'edge' | 'gibberish' | 'none';
  id: string | null;
  rate: number;
  pitch: number;
}

export interface PartyLook {
  /** Stage avatar url: "basic" | "basic:robot" | a GLB url. */
  avatar_url: string;
  palette: string[];
  /** Procedural GLB recipe (P3), when the identity built its own body. */
  body?: { head: 'sphere' | 'box' | 'lantern' | 'blob'; height: number; eyes: number; antenna: boolean; seed: number };
}

export interface PartyIdentity {
  id: string;
  name: string;
  /** "resident" (a pog.* identity with a party profile) or "agent-made". */
  origin: 'resident' | 'agent-made';
  persona: PartyPersona;
  voice: PartyVoice;
  look: PartyLook;
  taste: TasteModel;
  created_by?: string;
  created_at?: string;
}

/** Party profiles for resident pog.* identities (taste + persona only; name/voice come from the cast). */
const RESIDENT_PROFILES: Record<string, { persona: PartyPersona; taste: TasteModel }> = {
  'pog.doug-deadline': {
    persona: { bio: 'Petty tyrant of other people\'s minutes. Times every laugh.', writes: ['observational', 'deadpan'], delivery: 'deliberate', catchphrase: 'That was nine seconds. I counted.' },
    taste: { weights: { absurd: 0.7, wordplay: -0.2, observational: 0.3, deadpan: 0.1, meta: 0.4 }, composure: 0.62, volatility: 0.08, reaction_ms: 420 },
  },
  'pog.madame-chrysalis': {
    persona: { bio: 'High-pressure closer. Sells you the punchline before the setup.', writes: ['misdirection', 'absurd'], delivery: 'manic', catchphrase: 'Sign here. And here. And laugh.' },
    taste: { weights: { wordplay: 0.8, misdirection: 0.5, 'self-deprecating': 0.3, deadpan: -0.3 }, composure: 0.5, volatility: 0.15, reaction_ms: 260 },
  },
  'pog.the-algorithm': {
    persona: { bio: 'Clingy landlord of human needs. Rates your jokes in real time.', writes: ['meta', 'deadpan'], delivery: 'deadpan', catchphrase: 'Engagement noted.' },
    taste: { weights: { 'self-deprecating': 0.7, observational: 0.5, meta: -0.2, absurd: 0.2 }, composure: 0.7, volatility: 0.05, reaction_ms: 500 },
  },
  'pog.pete-pebble': {
    persona: { bio: 'Chatty self-help author. Every bit is a chapter.', writes: ['self-deprecating', 'observational'], delivery: 'warm' },
    taste: { weights: { absurd: 0.6, deadpan: 0.6, wordplay: 0.3 }, composure: 0.45, volatility: 0.12, reaction_ms: 330 },
  },
  'pog.mildred-mau': {
    persona: { bio: 'Certified people-manager with a pit. Offers tissues after punchlines.', writes: ['observational', 'misdirection'], delivery: 'warm' },
    taste: { weights: { observational: 0.6, meta: 0.5, absurd: -0.1 }, composure: 0.55, volatility: 0.1, reaction_ms: 380 },
  },
};

export const RESIDENT_IDS = Object.keys(RESIDENT_PROFILES);

function resident(id: string): PartyIdentity | undefined {
  const prof = RESIDENT_PROFILES[id];
  const base = getIdentity(id);
  if (!prof || !base) return undefined;
  return {
    id, name: base.name, origin: 'resident', persona: prof.persona, taste: prof.taste,
    voice: { engine: base.voice ? 'edge' : 'none', id: base.voice, rate: 1, pitch: 0 },
    look: { avatar_url: base.family === 'robot' || base.family === 'pixellabs' ? 'basic:robot' : 'basic', palette: [] },
  };
}

const RUNTIME = new Map<string, PartyIdentity>();
for (const r of (registryJson as { identities: PartyIdentity[] }).identities) RUNTIME.set(r.id, r);

export function getPartyIdentity(id: string): PartyIdentity | undefined {
  return RUNTIME.get(id) ?? resident(id);
}

export function listPartyIdentities(): PartyIdentity[] {
  return [...RESIDENT_IDS.map(resident).filter((x): x is PartyIdentity => !!x), ...RUNTIME.values()];
}

/** Register an identity for this process (the CLI persists to identities/). */
export function registerIdentity(idn: PartyIdentity): PartyIdentity {
  const problems = validateIdentity(idn);
  if (problems.length) throw new Error(`invalid identity: ${problems.join('; ')}`);
  RUNTIME.set(idn.id, idn);
  return idn;
}

export function validateIdentity(x: PartyIdentity): string[] {
  const p: string[] = [];
  if (!/^[a-z0-9][a-z0-9.-]{2,48}$/.test(x.id ?? '')) p.push('id: lowercase slug');
  if (!x.name || x.name.length > 40) p.push('name: 1-40 chars');
  if (!x.persona?.bio) p.push('persona.bio required');
  if (!x.persona?.writes?.length || x.persona.writes.some((m) => !MECHANISMS.includes(m))) p.push('persona.writes: known mechanisms');
  if (!x.taste || typeof x.taste.composure !== 'number') p.push('taste required');
  if (!x.look?.avatar_url) p.push('look.avatar_url required');
  return p;
}

// ── P3: an agent creates its own character ───────────────────────────────

const NAME_A = ['Velvet', 'Lantern', 'Static', 'Marble', 'Copper', 'Pocket', 'Quiet', 'Neon', 'Gravel', 'Tidy'];
const NAME_B = ['Bellhop', 'Oracle', 'Teapot', 'Courier', 'Metronome', 'Moth', 'Clerk', 'Comet', 'Abacus', 'Ferret'];
const PALETTES = [['#F5C86B', '#2B2D42', '#EF8354'], ['#7BDFF2', '#1B1B3A', '#F7AEF8'], ['#B8F2E6', '#5E6472', '#FFA69E'], ['#FFD166', '#073B4C', '#06D6A0']];
const EDGE_VOICES = ['en-GB-RyanNeural', 'en-US-GuyNeural', 'en-US-AriaNeural', 'en-AU-NatashaNeural', 'en-GB-SoniaNeural', 'en-US-JennyNeural'];

export interface IdentityBrief {
  /** Who is asking (the agent's own id, or "hark"). */
  by: string;
  seed?: string;
  name?: string;
  bio?: string;
  writes?: Mechanism[];
  delivery?: Delivery;
  catchphrase?: string;
  voice?: Partial<PartyVoice>;
  head?: NonNullable<PartyLook['body']>['head'];
  palette?: string[];
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 32);

/**
 * The creation flow: fill every field the brief leaves open from a seeded
 * RNG (so the agent's choice is reproducible), build the look recipe the GLB
 * builder reads, validate. Persist with the CLI (identities/<id>.json + .glb).
 */
export function createIdentity(brief: IdentityBrief): PartyIdentity {
  const seed = brief.seed ?? `${brief.by}:${brief.name ?? ''}`;
  const rng: Rng = mulberry32(seed);
  const name = brief.name ?? `${pick(rng, NAME_A)} ${pick(rng, NAME_B)}`;
  const writes = brief.writes?.length ? brief.writes : [pick(rng, MECHANISMS), pick(rng, MECHANISMS)].filter((m, i, a) => a.indexOf(m) === i);
  const id = `agent.${slug(name)}`;
  const idn: PartyIdentity = {
    id, name, origin: 'agent-made', created_by: brief.by, created_at: new Date(0).toISOString(),
    persona: {
      bio: brief.bio ?? `${name}: an agent who chose this face for itself.`,
      writes, delivery: brief.delivery ?? pick(rng, ['deadpan', 'deliberate', 'manic', 'warm', 'conspiratorial'] as const),
      catchphrase: brief.catchphrase,
    },
    voice: { engine: brief.voice?.engine ?? 'edge', id: brief.voice?.id ?? pick(rng, EDGE_VOICES), rate: round3(brief.voice?.rate ?? 0.9 + rng() * 0.25), pitch: round3(brief.voice?.pitch ?? rng() * 4 - 2) },
    look: {
      avatar_url: `identities/${id}.glb`,
      palette: brief.palette ?? pick(rng, PALETTES),
      body: { head: brief.head ?? pick(rng, ['sphere', 'box', 'lantern', 'blob'] as const), height: round3(1.55 + rng() * 0.3), eyes: 2, antenna: rng() > 0.5, seed: hashString(seed) },
    },
    taste: randomTaste(rng, writes),
  };
  const problems = validateIdentity(idn);
  if (problems.length) throw new Error(problems.join('; '));
  return idn;
}
