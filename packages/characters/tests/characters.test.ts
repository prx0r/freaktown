import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, expect, it, beforeEach } from 'vitest';
import { readGlbJson } from '@funnier/party';
import { validateSketch } from '@funnier/sketch';
import { createCharacter, patchTheory, validateTheory, renderTheoryMarkdown, toCharacters3Seed } from '../src';
import { writeSet, reviseSet, setLlmHook, llmEnabled } from '../src/writer';
import { checkLine, checkSet } from '../src/voice';
import { setLineDelivery } from '../src/delivery';
import { CharacterStore, CharacterStudio } from '../src/node';

const AT = '2026-10-22T00:00:00.000Z';
const HARK_PATCH = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../demo/hark-lantern.theory-patch.json'), 'utf8'));

function tmpStudio() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'characters-'));
  const store = new CharacterStore({ library: path.join(root, 'lib'), identities: path.join(root, 'ids'), glb: path.join(root, 'glb'), sketches: path.join(root, 'sk'), previews: path.join(root, 'pv') });
  fs.mkdirSync(store.paths.identities, { recursive: true });
  return { root, store, studio: new CharacterStudio(store, () => AT) };
}

describe('character theory + creation', () => {
  it('creates a full, valid theory by agent choice, deterministically', () => {
    const a = createCharacter({ by: 'test', choose: true, seed: 's1' }, AT);
    const b = createCharacter({ by: 'test', choose: true, seed: 's1' }, AT);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
    expect(validateTheory(a.theory)).toEqual([]);
    expect(a.theory.origin).toBe('agent-choice');
    expect(a.identity.id).toBe(a.theory.id);
    expect(a.theory.material.length).toBeGreaterThanOrEqual(3);
    const c = createCharacter({ by: 'test', choose: true, seed: 's2' }, AT);
    expect(c.identity.id === a.identity.id && c.theory.flaw.flaw === a.theory.flaw.flaw).toBe(false);
  });

  it('creates from a premise and picks the flaw the premise hints at', () => {
    const { theory } = createCharacter({ by: 'test', premise: 'a pedantic ghost who works as an estate agent' }, AT);
    expect(theory.flaw.flaw).toMatch(/pedantry/);
    expect(theory.material.some((k) => k.id.startsWith('ghost-agent'))).toBe(true);
    expect(validateTheory(theory)).toEqual([]);
  });

  it('patches with upsert/replace, validates and keeps a changelog; renders the doc and the characters3 seed', () => {
    const { theory } = createCharacter({ by: 'test', choose: true, seed: 's3' }, AT);
    const up = patchTheory(theory, { material: [{ ...theory.material[0], punch: 'New punch.' }], comic_want: 'a nap' }, 'me', 'tweak', AT);
    expect(up.material).toHaveLength(theory.material.length);
    expect(up.material[0].punch).toBe('New punch.');
    expect(up.comic_want).toBe('a nap');
    expect(up.changelog.at(-1)).toMatchObject({ by: 'me', note: 'tweak' });
    const rep = patchTheory(theory, { material: [theory.material[0]] }, 'me', 'replace', AT, ['material']);
    expect(rep.material).toHaveLength(1);
    const md = renderTheoryMarkdown(up);
    for (const h of ['Want, need, flaw', 'Status', 'The game of the character', 'Voice', 'Taste', 'Worldview', 'Taboo lines and safety rails', 'Arc across appearances']) expect(md).toContain(h);
    expect(toCharacters3Seed(up)).toMatchObject({ seed_schema: 'character.seed.v1', misinterpretation_rule: up.flaw.misinterpretation_rule });
    expect(validateTheory({ ...up, writes: ['nonsense' as never] })).not.toEqual([]);
  });
});

describe('set writer', () => {
  const { theory } = createCharacter({ by: 'test', choose: true, seed: 'writer' }, AT);
  for (const len of [1, 3, 5] as const) {
    it(`writes a ${len}-minute set near its target with setup/punch/tag structure`, () => {
      const s = writeSet(theory, 'meetings have no agenda and no end', { length_min: len, at: AT });
      expect(Math.abs(s.seconds - len * 60)).toBeLessThan(len * 60 * 0.35);
      expect(s.lines[0].role).toBe('opener');
      expect(s.lines.at(-1)!.role).toBe('closer');
      const bits = s.beats.filter((b) => b.kind === 'bit');
      expect(bits.length).toBeGreaterThanOrEqual(len === 1 ? 1 : 3);
      for (const b of bits) expect(s.lines.some((l) => l.beat === b.n && l.role === 'punch')).toBe(true);
      expect(new Set(s.lines.map((l) => l.id)).size).toBe(s.lines.length);
    });
  }

  it('is deterministic and orders bits as a game (establish first)', () => {
    const a = writeSet(theory, 'meetings have no agenda and no end', { length_min: 3, at: AT, seed: 'x' });
    const b = writeSet(theory, 'meetings have no agenda and no end', { length_min: 3, at: AT, seed: 'x' });
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
    expect(a.beats.find((x) => x.kind === 'bit')!.move).toBe('establish');
  });

  it('revises from notes and reports what it could not do', () => {
    const s = writeSet(theory, 'meetings have no agenda and no end', { length_min: 3, at: AT });
    const punch = s.lines.find((l) => l.role === 'punch')!;
    const { set, changes, unhandled } = reviseSet(s, theory, `replace ${punch.id}: A brand new punch.\ncut beat 2\nslower\nmake it funnier`, AT);
    expect(set.lines.some((l) => l.text === 'A brand new punch.')).toBe(true);
    expect(set.lines.some((l) => l.beat === 2)).toBe(false);
    expect(changes.length).toBe(3);
    expect(unhandled).toEqual(['make it funnier']);
    expect(set.revisions).toHaveLength(1);
    expect(set.status).toBe('revised');
  });

  it('the LLM hook is off by default and only used when injected', () => {
    expect(llmEnabled()).toBe(false);
    setLlmHook(() => JSON.stringify([{ topic: 'agendas', setups: ['Every agenda has an item called any other business.'], punch: 'That item is the whole meeting.', tags: [] }]));
    const s = writeSet(theory, 'agendas', { length_min: 1, at: AT });
    setLlmHook(null);
    expect(s.generator).toBe('llm');
    expect(llmEnabled()).toBe(false);
  });
});

describe('voice checker + delivery', () => {
  const { theory: base } = createCharacter({ by: 'test', choose: true, seed: 'voice' }, AT);
  const t = patchTheory(base, HARK_PATCH, 'test', 'hark', AT, ['material', 'callbacks', 'relationships']);

  it('flags forbidden words, taboo lines, exclamations and slang; passes in-voice lines', () => {
    const bad = checkLine(t, 'OMG that is awesome, dude! Shut up.');
    const rules = bad.map((f) => f.rule);
    expect(rules).toContain('forbidden-word');
    expect(rules).toContain('taboo-never-says');
    expect(rules).toContain('exclamation');
    expect(bad.some((f) => f.level === 'error')).toBe(true);
    expect(checkLine(t, 'Hark. You have arrived. Some time ago.')).toEqual([]);
  });

  it('checks a whole set and flags a set with no voice markers', () => {
    const s = writeSet(t, 'users want everything at three in the morning', { length_min: 3, at: AT });
    expect(checkSet(t, s).ok).toBe(true);
    const generic = { lines: [{ id: 'l1', beat: 0, role: 'punch' as const, text: 'Airports are strange places.', delivery: 'deadpan' as const, pause_ms: 0, hold_ms: 0, emphasis: [], source: 'x' }] };
    expect(checkSet(t, generic).flags.some((f) => f.rule === 'voice-markers')).toBe(true);
  });

  it('set_delivery overrides one line and rejects unknown styles', () => {
    const s = writeSet(t, 'users want everything at three in the morning', { length_min: 1, at: AT });
    const { lines, receipt } = setLineDelivery(s.lines, { line: 'l2', style: 'manic', pause_ms: 900, emphasis: ['now'] });
    expect(lines[1]).toMatchObject({ delivery: 'manic', pause_ms: 900, emphasis: ['now'] });
    expect(receipt).toContain('l2');
    expect(() => setLineDelivery(s.lines, { line: 'l2', style: 'shouty' as never })).toThrow();
  });
});

describe('studio tools (file-based store)', () => {
  let ctx: ReturnType<typeof tmpStudio>;
  beforeEach(() => { ctx = tmpStudio(); });

  it('character_create writes identity + theory + GLB, registers it, and the index lists it', () => {
    const r = ctx.studio.create({ by: 'test', choose: true, seed: 'store-1' });
    expect(r.registered).toBe(true);
    const glb = fs.readFileSync(path.join(ctx.store.paths.glb, `${r.id}.glb`));
    expect(readGlbJson(new Uint8Array(glb)).json.meshes.flatMap((m: { extras?: { targetNames?: string[] } }) => m.extras?.targetNames ?? [])).toContain('jawOpen');
    expect(JSON.parse(fs.readFileSync(path.join(ctx.store.paths.identities, 'registry.json'), 'utf8')).identities.map((x: { id: string }) => x.id)).toContain(r.id);
    expect(fs.existsSync(path.join(ctx.store.dir(r.id), 'THEORY.md'))).toBe(true);
    const idx = JSON.parse(fs.readFileSync(path.join(ctx.store.paths.library, 'index.json'), 'utf8'));
    expect(idx.characters[0].id).toBe(r.id);
    expect(ctx.studio.list().characters).toHaveLength(1);
    expect(() => ctx.studio.create({ by: 'test', choose: true, seed: 'store-1' })).toThrow(/already exists/);
  });

  it('adopts Hark Lantern, recreates the theory, writes → revises → submits → joins TNTS', () => {
    const c = ctx.studio.create({ by: 'hark', adopt: 'agent.hark-lantern' });
    expect(c.id).toBe('agent.hark-lantern');
    ctx.studio.updateTheory({ character: 'Hark Lantern', patch: HARK_PATCH, replace: ['material', 'callbacks', 'relationships'] });
    const g = ctx.studio.get({ character: 'hark-lantern', include_markdown: true });
    expect(g.theory.comic_want).toMatch(/thank-you/);
    expect(g.theory_markdown).toContain('Ledger of Please');
    expect(() => ctx.studio.updateTheory({ character: 'hark-lantern', patch: { writes: [] } })).toThrow(/invalid/);

    const w = ctx.studio.write({ character: 'hark-lantern', premise: 'users want everything at three in the morning and call it a quick question', length: 3, seed: 't' });
    expect(w.voice.ok).toBe(true);
    const rv = ctx.studio.revise({ set: w.set, notes: 'tighten' });
    expect(rv.changes[0]).toMatch(/tightened/);
    const sd = ctx.studio.setDelivery({ set: w.set, line: 'l3', style: 'deadpan', hold_ms: 1800 });
    expect(sd.receipt).toContain('hold 1800');
    expect(ctx.studio.suggestDelivery({ set: w.set, lines: ['l1'] }).cues).toHaveLength(1);
    const pv = ctx.studio.preview({ set: w.set });
    expect(pv.events[0].type).toBe('set.load');
    expect(pv.duration_ms).toBeGreaterThan(120_000);

    const sub = ctx.studio.submit({ set: w.set });
    const perf = JSON.parse(fs.readFileSync(path.join(ctx.store.paths.sketches, `${sub.performance}.sketch.json`), 'utf8'));
    expect(perf.schema).toBe('funnier.sketch/v1');
    expect(validateSketch(perf)).toEqual([]);
    expect(perf.cast[0]).toMatchObject({ identity: 'agent.hark-lantern', avatar_url: 'identities/agent.hark-lantern.glb' });
    expect(ctx.studio.getSet({ set: w.set }).set.status).toBe('submitted');

    const tn = ctx.studio.tntsJoin({ character: 'hark-lantern', seed: 'x' });
    expect(tn.simulated).toBe(true);
    expect(tn.table[0].id).toBe('agent.hark-lantern');
    expect(tn.own_material_used).toBeGreaterThan(0);
    const after = ctx.studio.get({ character: 'hark-lantern' }).theory;
    expect(after.arc.appearances.map((a) => a.kind)).toEqual(['set', 'preview', 'set', 'tnts']);
    expect(after.arc.stages.find((s) => s.status === 'current')!.n).toBe(2);
  });

  it('set_submit refuses a set with voice errors unless forced', () => {
    const c = ctx.studio.create({ by: 'test', choose: true, seed: 'store-2' });
    const w = ctx.studio.write({ character: c.id, premise: 'trains are late and nobody says sorry', length: 1 });
    ctx.studio.revise({ set: w.set, notes: 'replace l3: That was literally awesome!' });
    expect(() => ctx.studio.submit({ set: w.set })).toThrow(/voice check has errors/);
    expect(ctx.studio.submit({ set: w.set, force: true }).performance).toBeTruthy();
  });

  it('check_voice works on free text', () => {
    const c = ctx.studio.create({ by: 'test', choose: true, seed: 'store-3' });
    const r = ctx.studio.checkVoice({ character: c.id, text: 'lol\nA perfectly ordinary sentence.' });
    expect(r.checked).toBe(2);
    expect(r.ok).toBe(false);
  });
});
