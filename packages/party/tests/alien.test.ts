import { describe, expect, it } from 'vitest';
import { compile, validateRundown } from '@funnier/newsroom';
import { textMouth } from '../../stage-runtime/src/sets/textMouth';
import { alienLine, alienNewsRundown, alienPhonology, createAlienAnchors, POLITICIAN_CARD_URL, visemesOfText } from '../src/alien';
import { buildIdentityMeshes } from '../src/glb';
import { mulberry32 } from '../src/rng';

describe('Alien News (P5)', () => {
  it('the phoneme generator is seeded, consonant-initial and one vowel group per syllable', () => {
    const ph = alienPhonology('phonology:test');
    expect(alienPhonology('phonology:test')).toEqual(ph);
    expect(alienPhonology('phonology:other')).not.toEqual(ph);
    const a = alienLine(ph, mulberry32('x'), 12);
    expect(alienLine(ph, mulberry32('x'), 12)).toEqual(a);
    for (const s of a.syllables) {
      expect(s.text).toMatch(/^[^aeiouy]+[aeiou]+[^aeiouy]*$/);
      expect((s.text.match(/[aeiouy]+/g) ?? []).length).toBe(1);
    }
    // the stage's text mouth sees exactly the generator's syllables and visemes
    expect(visemesOfText(a.text)).toEqual(a.syllables.map((s) => s.viseme));
  });

  it('gibberish drives the stage mouth: one open/close per syllable with that syllable\'s viseme', () => {
    const ph = alienPhonology('phonology:mouth');
    const line = alienLine(ph, mulberry32('m'), 6);
    const n = line.syllables.length;
    const dur = 4000;
    const speech = dur * 0.92;
    const seen: string[] = [];
    for (let k = 0; k < n; k++) {
      const s = textMouth(line.text, dur, ((k + 0.5) / n) * speech); // middle of syllable k
      expect(s.open).toBeGreaterThan(0.5);
      const top = Object.entries(s.visemes).sort((x, y) => y[1] - x[1])[0][0];
      seen.push(top);
    }
    expect(seen).toEqual(line.syllables.map((s) => s.viseme));
  });

  it('two original anchors come from createIdentity (gibberish voice, alien bodies)', () => {
    const [z, m] = createAlienAnchors();
    expect(z).toMatchObject({ id: 'agent.zorvex-quillam', origin: 'agent-made', created_by: 'hark', voice: { engine: 'gibberish' }, look: { body: { head: 'dome', eyes: 3, antenna: true } } });
    expect(m).toMatchObject({ id: 'agent.mib-trellune', voice: { engine: 'gibberish' }, look: { body: { head: 'blob', eyes: 1 } } });
    const face = (idn: typeof z) => buildIdentityMeshes(idn).find((x) => x.name === 'face')!;
    const fz = face(z), fm = face(m);
    expect(fz.part.pos.length / 3).toBe(24 + 3 * 15);
    expect(fm.part.pos.length / 3).toBe(24 + 15);
    expect(Object.keys(fz.morphs!)).toContain('jawOpen');
  });

  it('builds a valid 45–60 s rundown with subtitles and an original caricature card', () => {
    const { rundown, lines } = alienNewsRundown();
    expect(validateRundown(rundown)).toEqual({ ok: true, errors: [] });
    const c = compile(rundown);
    expect(c.duration_ms).toBeGreaterThanOrEqual(45_000);
    expect(c.duration_ms).toBeLessThanOrEqual(60_000);
    const said = c.events.filter((e) => e.type === 'dialogue.line');
    expect(said.length).toBe(lines.length);
    expect(said.every((e) => typeof e.payload.subtitle === 'string')).toBe(true);
    const img = c.events.filter((e) => e.type === 'overlay.headline' && e.payload.image_url);
    expect(img.length).toBeGreaterThan(0); // the story card (re-shown after cut-aways)
    for (const e of img) expect(e.payload).toMatchObject({ text: 'Earth man at podium very sure about everything', image_url: POLITICIAN_CARD_URL, image_license: 'original' });
    expect(JSON.stringify(rundown)).not.toMatch(/\.(jpe?g|png|webp)\b/i); // no photo assets
    expect(c.events.find((e) => e.type === 'set.theme')!.payload).toMatchObject({ brand: 'Alien News' });
    // subtitles are optional
    const quiet = compile(alienNewsRundown({ subtitles: false }).rundown);
    expect(quiet.events.some((e) => e.type === 'dialogue.line' && e.payload.subtitle)).toBe(false);
  });
});
