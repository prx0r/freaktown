/**
 * File-based, git-friendly storage. One folder per character:
 *
 *   packages/characters/library/<slug>/
 *     theory.json                 funnier.character-theory/v1 (source of truth)
 *     THEORY.md                   generated theory doc
 *     sets/<set-id>.json|.md      funnier.character-set/v1 + readable script
 *     performances/<id>.sketch.json   submitted funnier.sketch/v1
 *   packages/characters/library/index.json   catalog the /characters3 page imports
 *
 * Identities stay where every room reads them (the party CLI layout):
 *   packages/party/identities/<id>.json + registry.json
 *   apps/live/public/identities/<id>.glb   (procedural body, ARKit morphs)
 * Submitted performances are also copied to apps/live/public/sketches/ so
 * /sketch/<id> can play them. Rendered previews (MP4) go to var/ (gitignored).
 *
 * Stable JSON (2-space, trailing newline) so diffs stay small. Every path can
 * be redirected with env vars (tests use a temp dir).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { identityGlb, validateIdentity, type PartyIdentity } from '@funnier/party';
import { renderTheoryMarkdown, validateTheory } from '../theory';
import { setToText } from '../writer';
import type { CharacterSet, CharacterTheory } from '../types';

const here = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(here, '../../../..');

export interface StorePaths { library: string; identities: string; glb: string; sketches: string; previews: string }

export function defaultPaths(env: NodeJS.ProcessEnv = process.env): StorePaths {
  const r = (p: string) => path.resolve(REPO_ROOT, p);
  return {
    library: env.CHARACTERS_LIBRARY ? path.resolve(env.CHARACTERS_LIBRARY) : r('packages/characters/library'),
    identities: env.PARTY_IDENTITIES_DIR ? path.resolve(env.PARTY_IDENTITIES_DIR) : r('packages/party/identities'),
    glb: env.CHARACTERS_GLB_DIR ? path.resolve(env.CHARACTERS_GLB_DIR) : r('apps/live/public/identities'),
    sketches: env.CHARACTERS_SKETCH_DIR ? path.resolve(env.CHARACTERS_SKETCH_DIR) : r('apps/live/public/sketches'),
    previews: env.CHARACTERS_PREVIEW_DIR ? path.resolve(env.CHARACTERS_PREVIEW_DIR) : r('var/characters-previews'),
  };
}

const json = (x: unknown) => JSON.stringify(x, null, 2) + '\n';
const read = <T>(p: string): T => JSON.parse(fs.readFileSync(p, 'utf8')) as T;
const write = (p: string, s: string | Uint8Array) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, s); };
export const slugOf = (id: string) => id.replace(/^[a-z]+\./, '');

export interface CatalogEntry { id: string; name: string; logline: string; origin: string; avatar_url: string; theory: CharacterTheory; theory_md: string; sets: CharacterSet[]; performances: string[] }
export interface Catalog { schema: 'funnier.characters-catalog/v1'; characters: CatalogEntry[] }

export class CharacterStore {
  constructor(readonly paths: StorePaths = defaultPaths()) {}

  dir(id: string) { return path.join(this.paths.library, slugOf(id)); }

  ids(): string[] {
    if (!fs.existsSync(this.paths.library)) return [];
    return fs.readdirSync(this.paths.library).filter((d) => fs.existsSync(path.join(this.paths.library, d, 'theory.json'))).sort()
      .map((d) => read<CharacterTheory>(path.join(this.paths.library, d, 'theory.json')).id);
  }

  /** Resolve "agent.hark-lantern" | "hark-lantern" | "Hark Lantern" to an id with a theory. */
  resolve(ref: string): string {
    const r = ref.trim().toLowerCase();
    const ids = this.ids();
    const hit = ids.find((id) => id === r || slugOf(id) === r || this.theory(id).name.toLowerCase() === r);
    if (!hit) throw new Error(`unknown character "${ref}". Known: ${ids.join(', ') || '(none yet: call character_create)'}`);
    return hit;
  }

  hasTheory(id: string) { return fs.existsSync(path.join(this.dir(id), 'theory.json')); }
  theory(id: string): CharacterTheory { return read<CharacterTheory>(path.join(this.dir(id), 'theory.json')); }

  saveTheory(t: CharacterTheory): string[] {
    const problems = validateTheory(t);
    if (problems.length) throw new Error(`invalid theory: ${problems.join('; ')}`);
    write(path.join(this.dir(t.id), 'theory.json'), json(t));
    write(path.join(this.dir(t.id), 'THEORY.md'), renderTheoryMarkdown(t));
    return [path.join(this.dir(t.id), 'theory.json'), path.join(this.dir(t.id), 'THEORY.md')];
  }

  identity(id: string): PartyIdentity | undefined {
    const p = path.join(this.paths.identities, `${id}.json`);
    if (fs.existsSync(p)) return read<PartyIdentity>(p);
    const reg = path.join(this.paths.identities, 'registry.json');
    if (fs.existsSync(reg)) return read<{ identities: PartyIdentity[] }>(reg).identities.find((x) => x.id === id);
    return undefined;
  }

  /** Persist the identity the way the party CLI does: <id>.json, regenerated registry.json, procedural GLB. */
  saveIdentity(idn: PartyIdentity): { files: string[]; glb_bytes: number } {
    const problems = validateIdentity(idn);
    if (problems.length) throw new Error(`invalid identity: ${problems.join('; ')}`);
    const dir = this.paths.identities;
    write(path.join(dir, `${idn.id}.json`), json(idn));
    const all: PartyIdentity[] = fs.readdirSync(dir).filter((f) => f.endsWith('.json') && f !== 'registry.json').sort().map((f) => read<PartyIdentity>(path.join(dir, f)));
    write(path.join(dir, 'registry.json'), json({ identities: all }));
    const glb = identityGlb(idn);
    const gp = path.join(this.paths.glb, `${idn.id}.glb`);
    write(gp, glb);
    return { files: [path.join(dir, `${idn.id}.json`), path.join(dir, 'registry.json'), gp], glb_bytes: glb.length };
  }

  sets(id: string): CharacterSet[] {
    const d = path.join(this.dir(id), 'sets');
    if (!fs.existsSync(d)) return [];
    return fs.readdirSync(d).filter((f) => f.endsWith('.json')).sort().map((f) => read<CharacterSet>(path.join(d, f)));
  }

  findSet(setId: string): CharacterSet {
    for (const id of this.ids()) { const s = this.sets(id).find((x) => x.id === setId); if (s) return s; }
    throw new Error(`unknown set "${setId}"`);
  }

  saveSet(s: CharacterSet): string[] {
    const base = path.join(this.dir(s.character), 'sets', s.id);
    write(`${base}.json`, json(s));
    write(`${base}.md`, setToText(s));
    return [`${base}.json`, `${base}.md`];
  }

  savePerformance(id: string, performanceId: string, performance: unknown): string[] {
    const a = path.join(this.dir(id), 'performances', `${performanceId}.sketch.json`);
    const b = path.join(this.paths.sketches, `${performanceId}.sketch.json`);
    write(a, json(performance));
    write(b, json(performance));
    return [a, b];
  }

  performances(id: string): string[] {
    const d = path.join(this.dir(id), 'performances');
    return fs.existsSync(d) ? fs.readdirSync(d).filter((f) => f.endsWith('.sketch.json')).sort().map((f) => f.replace(/\.sketch\.json$/, '')) : [];
  }

  /** Regenerate library/index.json (what /characters3 imports). */
  rebuildIndex(): string {
    const characters: CatalogEntry[] = this.ids().map((id) => {
      const t = this.theory(id);
      const idn = this.identity(id);
      return { id, name: t.name, logline: t.logline, origin: t.origin, avatar_url: idn?.look.avatar_url ?? 'basic', theory: t, theory_md: renderTheoryMarkdown(t), sets: this.sets(id), performances: this.performances(id) };
    });
    const p = path.join(this.paths.library, 'index.json');
    write(p, json({ schema: 'funnier.characters-catalog/v1', characters } satisfies Catalog));
    return p;
  }

  rel(p: string) { return path.relative(REPO_ROOT, p) || p; }
}
