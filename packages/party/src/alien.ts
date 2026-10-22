/**
 * Alien News (P5) — two original alien anchors read the news in an invented
 * language. Everything here is offline and deterministic:
 *
 *   alienPhonology(seed)      a seeded sound system per anchor: consonant onsets,
 *                             single vowel-group nuclei, optional codas, word shape
 *   alienLine(ph, rng, n)     gibberish words built syllable by syllable, plus the
 *                             viseme each syllable lands on
 *   createAlienAnchors()      the two anchors, made through createIdentity()
 *                             (dome heads, three eyes / one eye, voice "gibberish")
 *   alienNewsRundown()        a funnier.newsroom.rundown/v1 the newsroom SDK renders:
 *                             gibberish reads (the text drives the mouth: one vowel
 *                             group per syllable → one open/close with that vowel's
 *                             viseme), optional funny subtitles, and an ORIGINAL drawn
 *                             caricature card of a generic blustery politician
 *
 * The visemes line up with the stage's text mouth (stage-runtime textMouth):
 * every syllable starts with a consonant and holds exactly one vowel group, so
 * the stage's syllable count and vowel → viseme map equal the generator's.
 * No TTS, no network, no real person: the caricature is a hand-drawn SVG with a
 * generic label ("EARTH POLITICIAN (GENERIC)").
 */
import type { RundownV1 } from '@funnier/newsroom';
import { createIdentity, type PartyIdentity } from './identity';
import { mulberry32, pick, type Rng } from './rng';

export type AlienViseme = 'aa' | 'ee' | 'ih' | 'oh' | 'ou';
/** Same first-vowel → viseme map as stage-runtime textMouth. */
const VOWEL_VIS: Record<string, AlienViseme> = { a: 'aa', e: 'ee', i: 'ih', o: 'oh', u: 'ou', y: 'ih' };

export interface AlienPhonology {
  seed: string;
  onsets: string[];
  nuclei: string[];
  codas: string[];
  /** Chance a syllable closes with a coda. */
  codaRate: number;
  /** Syllables per word [min, max]. */
  syllables: [number, number];
  /** Chance of a hyphen or apostrophe joint inside a word ("zor-vak", "k'tesh"). */
  jointRate: number;
}

export interface AlienSyllable { text: string; viseme: AlienViseme }
export interface AlienLine { text: string; words: string[]; syllables: AlienSyllable[] }

// Inventories: onsets/codas never contain a vowel letter (y included), nuclei are one vowel group.
const ONSETS = ['b', 'd', 'g', 'k', 'l', 'm', 'n', 'p', 'r', 's', 't', 'v', 'z', 'sh', 'th', 'kr', 'gl', 'bl', 'zh', 'q', 'x', 'vr', 'tl', 'fn', 'skr'];
const NUCLEI = ['a', 'e', 'i', 'o', 'u', 'aa', 'oo', 'ee', 'ou', 'ai', 'ei', 'ua'];
const CODAS = ['k', 'x', 'm', 'n', 'r', 'sh', 'z', 'th', 'rk', 'nk', 'b', 'p', 'ng'];

/** A seeded sound system: each anchor gets its own accent. */
export function alienPhonology(seed: string): AlienPhonology {
  const rng = mulberry32(`phonology:${seed}`);
  const take = (xs: string[], n: number) => { const pool = [...xs]; const out: string[] = []; while (out.length < n && pool.length) out.push(pool.splice(Math.floor(rng() * pool.length), 1)[0]); return out; };
  return {
    seed,
    onsets: take(ONSETS, 9 + Math.floor(rng() * 5)),
    nuclei: take(NUCLEI, 5 + Math.floor(rng() * 3)),
    codas: take(CODAS, 4 + Math.floor(rng() * 4)),
    codaRate: 0.2 + rng() * 0.25,
    syllables: rng() > 0.5 ? [1, 2] : [1, 3],
    jointRate: 0.1 + rng() * 0.15,
  };
}

/** One gibberish word: syllables of onset + nucleus (+ coda). */
export function alienWord(ph: AlienPhonology, rng: Rng): { word: string; syllables: AlienSyllable[] } {
  const n = ph.syllables[0] + Math.floor(rng() * (ph.syllables[1] - ph.syllables[0] + 1));
  const syllables: AlienSyllable[] = [];
  let word = '';
  for (let i = 0; i < n; i++) {
    const nuc = pick(rng, ph.nuclei);
    const syl = pick(rng, ph.onsets) + nuc + (rng() < ph.codaRate ? pick(rng, ph.codas) : '');
    if (i > 0 && rng() < ph.jointRate) word += rng() < 0.5 ? '-' : "'";
    word += syl;
    syllables.push({ text: syl, viseme: VOWEL_VIS[nuc[0]] ?? 'aa' });
  }
  return { word, syllables };
}

/** A gibberish line of `words` words; sentence case + an anchor-ish final punctuation. */
export function alienLine(ph: AlienPhonology, rng: Rng, words: number, end: '.' | '!' | '?' = '.'): AlienLine {
  const ws: string[] = [];
  const syllables: AlienSyllable[] = [];
  for (let i = 0; i < words; i++) { const w = alienWord(ph, rng); ws.push(w.word); syllables.push(...w.syllables); }
  let text = ws.join(' ');
  if (words > 5) { const k = 2 + Math.floor(rng() * (words - 3)); const parts = text.split(' '); parts[k] += ','; text = parts.join(' '); }
  text = text.charAt(0).toUpperCase() + text.slice(1) + end;
  return { text, words: ws, syllables };
}

/** Visemes the stage's text mouth will play for a line (vowel groups in order). */
export function visemesOfText(text: string): AlienViseme[] {
  return text.toLowerCase().split(/\s+/).filter(Boolean).flatMap((w) => (w.match(/[aeiouy]+/g) ?? []).map((g) => VOWEL_VIS[g[0]] ?? 'aa'));
}

// ── the anchors ──────────────────────────────────────────────────────────

export const ALIEN_ANCHOR_BRIEFS = [
  {
    by: 'hark', seed: 'alien-news:zorvex', name: 'Zorvex Quillam', head: 'dome' as const, eyes: 3, antenna: true,
    bio: 'Senior anchor from a moon that never asked to be visited. Reads Earth news like a weather warning.',
    writes: ['deadpan', 'observational'] as const, delivery: 'deadpan' as const, catchphrase: 'Kravash. (That is all.)',
    palette: ['#7CF29A', '#1B1B3A', '#F7AEF8'],
  },
  {
    by: 'hark', seed: 'alien-news:mib', name: 'Mib Trellune', head: 'blob' as const, eyes: 1, antenna: true,
    bio: 'Field correspondent turned co-anchor. Has been to Earth once and is still processing it.',
    writes: ['absurd', 'meta'] as const, delivery: 'manic' as const, catchphrase: 'Shoo-mak! (Back to you.)',
    palette: ['#B79CFF', '#2B2D42', '#FFD166'],
  },
];

/** The two anchors, created through the identity flow (voice: gibberish, no TTS). */
export function createAlienAnchors(): [PartyIdentity, PartyIdentity] {
  const [a, b] = ALIEN_ANCHOR_BRIEFS.map((x) => createIdentity({ ...x, writes: [...x.writes], voice: { engine: 'gibberish', id: `phonology:${x.seed}`, rate: 1, pitch: 0 } }));
  return [a, b];
}

// ── the show ─────────────────────────────────────────────────────────────

type Beat = { who: 0 | 1; words: number; end?: '.' | '!' | '?'; sub: string; emotion?: string };

/** The script: who speaks, how long (in gibberish words) and the subtitle. All original. */
export const ALIEN_NEWS_SCRIPT: Array<{ id: string; title: string; kind: 'open' | 'section' | 'close'; wall?: { headline: string; kicker?: string; body?: string; layout?: 'title' | 'headline' | 'numbers' | 'close'; figure?: string; image?: boolean }; beats: Beat[] }> = [
  {
    id: 'open', title: 'Open', kind: 'open', wall: { layout: 'title', headline: 'Alien News', kicker: 'Live from high orbit' },
    beats: [
      { who: 0, words: 10, sub: 'Good evening, galaxy. I am Zorvex Quillam.', emotion: 'neutral' },
      { who: 1, words: 8, end: '!', sub: 'And I am Mib. Tonight: Earth, still doing that.', emotion: 'happy' },
    ],
  },
  {
    id: 'leader', title: 'Top story', kind: 'section',
    wall: { headline: 'Earth man at podium very sure about everything', kicker: 'Top story', image: true },
    beats: [
      { who: 0, words: 11, sub: 'Our top story: an Earth leader spoke for ninety minutes today.' },
      { who: 0, words: 10, sub: 'Translators confirm the volume was the message.' },
      { who: 1, words: 10, end: '!', sub: 'He promised a better tomorrow and a much louder today.', emotion: 'surprised' },
      { who: 1, words: 10, sub: 'Our probe asked a follow-up question. The probe is being rebooted.' },
      { who: 0, words: 6, sub: '[translation: he pointed at the sky a lot]' },
    ],
  },
  {
    id: 'numbers', title: 'The numbers', kind: 'section',
    wall: { layout: 'numbers', figure: '144', headline: 'times a day an Earthling checks the small glowing rectangle', kicker: 'The numbers' },
    beats: [
      { who: 1, words: 10, sub: 'Earthlings check a small glowing rectangle one hundred and forty-four times a day.' },
      { who: 0, words: 8, sub: 'The rectangle has never once checked on them.' },
    ],
  },
  {
    id: 'weather', title: 'Weather', kind: 'section',
    wall: { headline: 'Earth weather: hot, then complaining, then hot again', kicker: 'Weather' },
    beats: [
      { who: 1, words: 8, end: '!', sub: 'Earth weather: hot, then complaining.' },
      { who: 0, words: 6, sub: 'Then hot again. Bring a small fan and a large opinion.' },
    ],
  },
  {
    id: 'close', title: 'Close', kind: 'close', wall: { layout: 'close', headline: 'Please return our probe', kicker: 'Alien News' },
    beats: [
      { who: 0, words: 8, sub: 'That is the news. Kravash.' },
      { who: 1, words: 6, end: '!', sub: 'Shoo-mak! And please return our probe.', emotion: 'happy' },
    ],
  },
];

export const POLITICIAN_CARD_URL = '/alien-news/politician-card.svg';

export interface AlienNewsOptions { seed?: string; subtitles?: boolean }

/** Build the Alien News rundown (newsroom SDK schema). */
export function alienNewsRundown(opts: AlienNewsOptions = {}): { rundown: RundownV1; anchors: [PartyIdentity, PartyIdentity]; lines: Array<{ id: string; who: string; text: string; subtitle: string; visemes: AlienViseme[] }> } {
  const anchors = createAlienAnchors();
  const phon = anchors.map((a) => alienPhonology(a.voice.id ?? a.id));
  const rng = mulberry32(`alien-news:${opts.seed ?? 'ep1'}`);
  const subs = opts.subtitles !== false;
  const lines: Array<{ id: string; who: string; text: string; subtitle: string; visemes: AlienViseme[] }> = [];
  const segments: RundownV1['segments'] = ALIEN_NEWS_SCRIPT.map((seg) => {
    const pieces: RundownV1['segments'][number]['stories'][number]['pieces'] = [];
    if (seg.wall) {
      pieces.push({
        type: 'wall', layout: seg.wall.layout ?? 'headline', headline: seg.wall.headline, kicker: seg.wall.kicker, body: seg.wall.body, figure: seg.wall.figure,
        ...(seg.wall.image ? { image_url: POLITICIAN_CARD_URL, image_license: 'original', credit: 'Original illustration' } : {}),
      });
    }
    if (seg.id === 'open') pieces.push({ type: 'ticker', items: ['Earth: still spinning', 'Moon: unimpressed', 'Probe: missing', 'Translation desk: on strike'] }, { type: 'jingle', kind: 'open' });
    seg.beats.forEach((b, i) => {
      const line = alienLine(phon[b.who], rng, b.words, b.end ?? '.');
      const id = `${seg.id}-${i + 1}`;
      lines.push({ id, who: anchors[b.who].name, text: line.text, subtitle: b.sub, visemes: line.syllables.map((s) => s.viseme) });
      pieces.push({ type: 'anchor_read', id, chair: b.who === 0 ? 'zorvex' : 'mib', text: line.text, ...(b.emotion ? { emotion: b.emotion } : {}), ...(subs ? { subtitle: b.sub } : {}) });
    });
    if (seg.id === 'close') pieces.push({ type: 'jingle', kind: 'close' });
    return { id: seg.id, title: seg.title, kind: seg.kind, stories: [{ id: `${seg.id}-story`, title: seg.title, ...(seg.wall?.image ? { source: { name: 'FUNNIER original illustration', license: 'original' } } : {}), pieces }] };
  });
  const rundown: RundownV1 = {
    schema: 'funnier.newsroom.rundown/v1', id: 'alien-news-ep1', title: 'Alien News', show_style: 'default-news', brand: 'Alien News',
    cast: { anchors: [
      { chair: 'zorvex', name: anchors[0].name, seat: 'anchor1', character_id: anchors[0].id, avatar_url: anchors[0].look.avatar_url },
      { chair: 'mib', name: anchors[1].name, seat: 'anchor2', character_id: anchors[1].id, avatar_url: anchors[1].look.avatar_url },
    ] },
    segments,
    meta: { generator: 'packages/party/src/alien.ts', language: 'invented (seeded phonology per anchor)', subtitles: subs, caricature: 'original SVG, generic label, no real likeness' },
  };
  return { rundown, anchors, lines };
}
