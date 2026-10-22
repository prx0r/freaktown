/**
 * The character theory model (funnier.character-theory/v1) and the set model
 * (funnier.character-set/v1). Plain JSON, git-friendly, schema'd in
 * ../schemas/character-theory.v1.json. Every field answers one craft question
 * (docs/CHARACTER-THEORY.md says which source the question comes from).
 */
import type { Delivery, Mechanism, MinuteRole, LineDelivery, TasteModel } from '@funnier/party';

export const THEORY_SCHEMA = 'funnier.character-theory/v1' as const;
export const SET_SCHEMA = 'funnier.character-set/v1' as const;

export type Attitude = 'weird' | 'hard' | 'scary' | 'stupid' | 'wonderful' | 'unfair';
export type StatusLevel = 'high' | 'low' | 'shifting';

/** A ready-to-perform joke kernel the writer can place (topic + attitude + premise → setup/punch/tags). */
export interface MaterialKernel {
  id: string;
  /** What it is about, in two or three words. The writer matches premises against topic + keywords. */
  topic: string;
  keywords: string[];
  attitude: Attitude;
  /** The opinion behind it (Carter: "because..."). Not performed verbatim unless used as a setup. */
  premise: string;
  setups: string[];
  /** Optional act-out lines (the character playing someone else), performed manic by default. */
  act_out?: string[];
  punch: string;
  tags: string[];
  mechanism: Mechanism;
  /** UCB game move this kernel makes when placed: establish the pattern, heighten it, explore why, or top it. */
  move: 'establish' | 'heighten' | 'explore' | 'top';
  /** If set, the closer can call this kernel back with this line. */
  callback?: string;
}

export interface Relationship {
  who: string;
  /** Identity id when the other party is a registered character. */
  identity?: string;
  dynamic: string;
  /** Kaplan's metaphorical relationship ("an overbooked hotel and its only bellhop"). */
  metaphor?: string;
  status: 'above' | 'below' | 'equal' | 'shifting';
}

export interface ArcStage { n: number; title: string; shift: string; status: 'done' | 'current' | 'planned' }

export interface Appearance { at: string; kind: 'set' | 'tnts' | 'preview'; ref: string; note?: string }

export interface CharacterTheory {
  schema: typeof THEORY_SCHEMA;
  id: string;
  name: string;
  /** One sentence: who they are and what they do on stage. */
  logline: string;
  /** The act in one line (what the character is "about"). */
  premise: string;
  /** How they introduce themselves in an opener ("a ghost who works as an estate agent"). */
  intro?: string;
  origin: 'premise' | 'agent-choice' | 'adopted';

  /** What they chase on stage (Kaplan "winning"; concrete, scene-sized). */
  comic_want: string;
  /** What they actually need and cannot see (the thing an arc could give them; sitcoms withhold it). */
  need: string;
  /** Vorhaus: the flaw that opens comic distance, plus what they cannot see about themselves. */
  flaw: { flaw: string; blind_spot: string; misinterpretation_rule: string; misreads: Array<{ trigger: string; as: string }> };
  /** Johnstone: status is something you DO. Played vs felt, and how the see-saw tips. */
  status: { plays: StatusLevel; to_audience: StatusLevel; felt: string; actual: string; see_saw: string };
  /** Vorhaus comic perspective + Carter attitude: how they see the world, and their take on it. */
  point_of_view: { attitude: Attitude[]; take: string; lens: string };
  /** UCB: the first unusual thing, the pattern, and the if-then moves that heighten/explore it. */
  game: { unusual_thing: string; pattern: string; heighten: string[]; explore: string[]; base_reality: string };
  voice: {
    register: string;
    sentence_shape: string;
    /** Max words per sentence before the checker flags it. */
    max_sentence_words: number;
    contractions: 'never' | 'sparingly' | 'freely';
    exclamations: boolean;
    verbal_tics: string[];
    signature_words: string[];
    forbidden_words: string[];
    /** Preferred substitutions the checker suggests (word -> in-voice word). */
    substitutions: Record<string, string>;
  };
  physicality: {
    delivery_default: Delivery;
    energy: number;
    pace: number;
    punchline_hold_ms: number;
    stillness: string;
    gestures: string[];
  };
  /** TNTS taste model (party TasteModel) plus the human-readable reasons it smiles or holds. */
  taste: TasteModel & { smiles_at: string[]; stone_face_at: string[] };
  /** Mechanisms the character writes in (party Mechanism ids). */
  writes: Mechanism[];
  /** Five sentences, their logic (characters3 philosophy block). */
  worldview: { ontology: string; epistemology: string; axiology: string; causality: string; agency: string };
  contradictions: string[];
  backstory_anchors: string[];
  catchphrases: string[];
  /** Running gags / runners the character returns to across sets. */
  callbacks: Array<{ id: string; runner: string; seed_line: string }>;
  /** Hard rails. The checker treats taboo hits as errors, not style notes. */
  taboo: { never_targets: string[]; never_topics: string[]; never_says: string[]; safety_rails: string[] };
  relationships: Relationship[];
  /** Vorhaus "humanity": the bridge back to the audience. */
  humanity: string;
  arc: { shape: 'flat' | 'slow-change' | 'circular'; stages: ArcStage[]; reset_rule: string; appearances: Appearance[] };
  /** Kernels the writer prefers over generated frames. */
  material: MaterialKernel[];
  props: string[];
  changelog: Array<{ at: string; by: string; note: string }>;
}

export interface SetLine {
  id: string;
  beat: number;
  role: MinuteRole;
  text: string;
  delivery: LineDelivery;
  pause_ms: number;
  hold_ms: number;
  emphasis: string[];
  /** Where the line came from: a theory kernel id, a frame id, a note, or "human". */
  source: string;
  mechanism?: Mechanism;
  callback_to?: string;
}

export interface SetBeat {
  n: number;
  kind: 'opener' | 'bit' | 'callback' | 'closer';
  topic: string;
  move: MaterialKernel['move'] | 'open' | 'close';
  source: string;
}

export interface SetRevision { at: string; notes: string; changes: string[] }

export interface CharacterSet {
  schema: typeof SET_SCHEMA;
  id: string;
  character: string;
  character_name: string;
  title: string;
  premise: string;
  length_min: 1 | 3 | 5;
  target_seconds: number;
  seconds: number;
  seed: string;
  generator: 'template' | 'llm';
  beats: SetBeat[];
  lines: SetLine[];
  revisions: SetRevision[];
  status: 'draft' | 'revised' | 'submitted';
  performance?: string;
}
