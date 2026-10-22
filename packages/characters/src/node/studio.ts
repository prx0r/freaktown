/**
 * The /characters3 studio: one method per MCP tool, plain JSON in and out.
 * The MCP server (server.ts) is a thin wrapper; tests call this directly.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { getPartyIdentity, readGlbJson, identityGlb, registerIdentity, type LineDelivery, type PartyIdentity } from '@funnier/party';
import { createCharacter, theoryFromIdentity, type CreateBrief } from '../create';
import { patchTheory, renderTheoryMarkdown, validateTheory } from '../theory';
import { reviseSet, setToText, writeSet } from '../writer';
import { setLineDelivery, suggestSetDelivery } from '../delivery';
import { checkLine, checkSet, report } from '../voice';
import { previewEvents, setToSketch, submitSet } from '../perform';
import { joinTnts } from '../tnts';
import type { Appearance, CharacterSet, CharacterTheory } from '../types';
import { CharacterStore, REPO_ROOT } from './store';

export type Clock = () => string;

export class CharacterStudio {
  constructor(readonly store = new CharacterStore(), private now: Clock = () => new Date().toISOString()) {}

  private identityOf(id: string): PartyIdentity {
    const idn = this.store.identity(id) ?? getPartyIdentity(id);
    if (!idn) throw new Error(`no identity record for ${id}`);
    if (!getPartyIdentity(id)) registerIdentity(idn);
    return idn;
  }

  private touch(id: string, a: Omit<Appearance, 'at'>): CharacterTheory {
    const t = this.store.theory(id);
    t.arc.appearances = [...t.arc.appearances, { at: this.now(), ...a }];
    // advance the arc pointer on submitted sets only (previews and TNTS games are logged, not arc beats)
    if (a.kind === 'set') {
      const n = t.arc.appearances.filter((x) => x.kind === 'set').length;
      const stage = Math.min(t.arc.stages.length, n);
      t.arc.stages = t.arc.stages.map((s) => ({ ...s, status: s.n < stage ? 'done' : s.n === stage ? 'current' : 'planned' }));
    }
    this.store.saveTheory(t);
    return t;
  }

  // ── characters ──────────────────────────────────────────────────────

  create(args: CreateBrief & { adopt?: string }) {
    const at = this.now();
    let identity: PartyIdentity;
    let theory: CharacterTheory;
    if (args.adopt) {
      const existing = this.store.identity(args.adopt) ?? getPartyIdentity(args.adopt);
      if (!existing) throw new Error(`adopt: no identity ${args.adopt}`);
      identity = existing;
      theory = this.store.hasTheory(existing.id) ? this.store.theory(existing.id) : theoryFromIdentity(existing, args.by, at);
    } else {
      ({ identity, theory } = createCharacter(args, at));
      if (this.store.hasTheory(identity.id)) throw new Error(`${identity.id} already exists (use character_update_theory, or pass a different name/seed)`);
    }
    const saved = this.store.saveIdentity(identity);
    if (!getPartyIdentity(identity.id)) registerIdentity(identity);
    const files = [...saved.files, ...this.store.saveTheory(theory)];
    files.push(this.store.rebuildIndex());
    const g = readGlbJson(identityGlb(identity));
    return {
      id: identity.id, name: identity.name, origin: theory.origin, logline: theory.logline, premise: theory.premise,
      game: theory.game.unusual_thing, want: theory.comic_want, flaw: theory.flaw.flaw, delivery: theory.physicality.delivery_default, catchphrase: theory.catchphrases[0] ?? null,
      glb: { path: this.store.rel(saved.files[2]), bytes: saved.glb_bytes, morphs: g.json.meshes.flatMap((m: { extras?: { targetNames?: string[] } }) => m.extras?.targetNames ?? []) },
      registered: true, files: files.map((f) => this.store.rel(f)),
    };
  }

  get(args: { character: string; include_markdown?: boolean }) {
    const id = this.store.resolve(args.character);
    const t = this.store.theory(id);
    return {
      identity: this.identityOf(id), theory: t, theory_markdown: args.include_markdown ? renderTheoryMarkdown(t) : undefined,
      sets: this.store.sets(id).map((s) => ({ id: s.id, title: s.title, length_min: s.length_min, seconds: s.seconds, status: s.status, revisions: s.revisions.length })),
      performances: this.store.performances(id),
    };
  }

  list() {
    return { characters: this.store.ids().map((id) => { const t = this.store.theory(id); return { id, name: t.name, logline: t.logline, origin: t.origin, delivery: t.physicality.delivery_default, sets: this.store.sets(id).length, appearances: t.arc.appearances.length }; }) };
  }

  updateTheory(args: { character: string; patch: Record<string, unknown>; note?: string; by?: string; replace?: string[] }) {
    const id = this.store.resolve(args.character);
    const next = patchTheory(this.store.theory(id), args.patch, args.by ?? 'agent', args.note ?? 'theory updated', this.now(), args.replace ?? []);
    const problems = validateTheory(next);
    if (problems.length) throw new Error(`patch rejected, theory would be invalid: ${problems.join('; ')}`);
    const files = this.store.saveTheory(next);
    files.push(this.store.rebuildIndex());
    return { id, changed: Object.keys(args.patch), material: next.material.length, changelog: next.changelog.length, files: files.map((f) => this.store.rel(f)) };
  }

  // ── sets ────────────────────────────────────────────────────────────

  private saveSet(s: CharacterSet) { const f = this.store.saveSet(s); f.push(this.store.rebuildIndex()); return f.map((x) => this.store.rel(x)); }

  write(args: { character: string; premise: string; length: 1 | 3 | 5; seed?: string; title?: string }) {
    const id = this.store.resolve(args.character);
    const t = this.store.theory(id);
    if (![1, 3, 5].includes(args.length)) throw new Error('length must be 1, 3 or 5 (minutes)');
    const s = writeSet(t, args.premise, { length_min: args.length, seed: args.seed, at: this.now(), title: args.title });
    const files = this.saveSet(s);
    const voice = checkSet(t, s);
    return { set: s.id, title: s.title, seconds: s.seconds, target_seconds: s.target_seconds, beats: s.beats.map((b) => `${b.n}:${b.kind}${b.kind === 'bit' ? `(${b.topic}/${b.move})` : ''}`), voice: { score: voice.score, ok: voice.ok, flags: voice.flags.length }, script: setToText(s), files };
  }

  getSet(args: { set: string }) { const s = this.store.findSet(args.set); return { set: s, script: setToText(s) }; }

  revise(args: { set: string; notes: string }) {
    const s = this.store.findSet(args.set);
    const t = this.store.theory(s.character);
    const { set, changes, unhandled } = reviseSet(s, t, args.notes, this.now());
    const files = this.saveSet(set);
    const voice = checkSet(t, set);
    return { set: set.id, seconds: set.seconds, changes, unhandled, voice: { score: voice.score, ok: voice.ok, flags: voice.flags }, script: setToText(set), files };
  }

  suggestDelivery(args: { set: string; lines?: string[] }) {
    const s = this.store.findSet(args.set);
    const t = this.store.theory(s.character);
    const sug = suggestSetDelivery(s.lines, t);
    const lines = s.lines.map((l, i) => (!args.lines?.length || args.lines.includes(l.id) ? sug[i] : l));
    const next = { ...s, lines };
    this.saveSet(next);
    return { set: s.id, cues: lines.filter((l) => !args.lines?.length || args.lines.includes(l.id)).map((l) => ({ line: l.id, role: l.role, style: l.delivery, pause_ms: l.pause_ms, hold_ms: l.hold_ms, emphasis: l.emphasis, text: l.text })) };
  }

  setDelivery(args: { set: string; line: string; style?: LineDelivery; pause_ms?: number; hold_ms?: number; emphasis?: string[] }) {
    const s = this.store.findSet(args.set);
    const { lines, receipt } = setLineDelivery(s.lines, args);
    this.saveSet({ ...s, lines });
    return { set: s.id, receipt };
  }

  checkVoice(args: { set?: string; character?: string; text?: string }) {
    if (args.set) { const s = this.store.findSet(args.set); return checkSet(this.store.theory(s.character), s); }
    if (!args.character || !args.text) throw new Error('pass set, or character + text');
    const t = this.store.theory(this.store.resolve(args.character));
    const lines = args.text.split(/\n+/).map((x) => x.trim()).filter(Boolean);
    return report(t, lines.flatMap((x, i) => checkLine(t, x, { id: `t${i + 1}` })), lines.length);
  }

  preview(args: { set: string; render?: boolean; clip_seconds?: number; out?: string; event_limit?: number }) {
    const s = this.store.findSet(args.set);
    const idn = this.identityOf(s.character);
    const ev = previewEvents(s, idn, args.event_limit ?? 120);
    this.touch(s.character, { kind: 'preview', ref: s.id });
    if (!args.render) return { ...ev, mp4: null, note: 'stage events only (pass render:true for an MP4; needs a built apps/live + Chromium)' };
    const sketch = setToSketch(s, idn);
    const tmp = path.join(os.tmpdir(), `${s.id}.sketch.json`);
    fs.writeFileSync(tmp, JSON.stringify(sketch));
    const out = path.resolve(args.out ?? path.join(this.store.paths.previews, `${s.id}.mp4`));
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const clip = Math.round((args.clip_seconds ?? 20) * 1000);
    const r = spawnSync(process.execPath, [path.join(REPO_ROOT, 'packages/sketch/cli/render.mjs'), tmp, '-o', out, '--to', String(clip), '--quality', 'low', '--size', '960x540'], { cwd: REPO_ROOT, encoding: 'utf8', timeout: 20 * 60_000, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    const ok = r.status === 0 && fs.existsSync(out);
    return { ...ev, events: ev.events.slice(0, 20), mp4: ok ? out : null, clip_ms: clip, render_log: (r.stdout + r.stderr).split('\n').filter(Boolean).slice(-8), note: ok ? 'rendered' : 'render failed: stage events returned instead (see render_log)' };
  }

  submit(args: { set: string; force?: boolean }) {
    const s = this.store.findSet(args.set);
    const t = this.store.theory(s.character);
    const voice = checkSet(t, s);
    if (!voice.ok && !args.force) throw new Error(`voice check has errors; fix them or pass force:true: ${voice.flags.filter((f) => f.level === 'error').map((f) => `${f.line}: ${f.message}`).join('; ')}`);
    const idn = this.identityOf(s.character);
    const sub = submitSet(s, idn, this.now());
    if (sub.problems.length) throw new Error(`performance invalid: ${sub.problems.join('; ')}`);
    const files = this.store.savePerformance(s.character, sub.performance.id, sub.performance);
    const next: CharacterSet = { ...s, status: 'submitted', performance: sub.performance.id };
    files.push(...this.store.saveSet(next));
    this.touch(s.character, { kind: 'set', ref: s.id, note: `${s.length_min}-min "${s.title}"` });
    files.push(this.store.rebuildIndex());
    return { performance: sub.performance.id, schema: sub.performance.schema, seconds: sub.seconds, beats: sub.performance.scenes[0].beats.length, play: `/sketch/${sub.performance.id}`, files: files.map((f) => this.store.rel(f)) };
  }

  tntsJoin(args: { character: string; seed?: string; opponents?: string[] }) {
    const id = this.store.resolve(args.character);
    const known = new Set(this.store.ids());
    const studio = (args.opponents ?? []).filter((o) => known.has(o)).map((o) => ({ idn: this.identityOf(o), theory: this.store.theory(o), sets: this.store.sets(o) }));
    const r = joinTnts(this.identityOf(id), this.store.theory(id), this.store.sets(id), { seed: args.seed, opponents: args.opponents, studio });
    this.touch(id, { kind: 'tnts', ref: r.seed, note: `winner ${r.winner ?? 'none'}` });
    this.store.rebuildIndex();
    return r;
  }
}
